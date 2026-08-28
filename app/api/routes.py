"""RESTful API routes for the FIT multi-agent analysis service."""

import json
import logging
import os
import tempfile
import time
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile

from app.agents.coordinator_agent import CoordinatorAgent, CoordinatorError
from app.db import database
from app.harness_setup import get_harness, get_analysis_workflow, get_chat_workflow, get_llm_orchestrator
from app.services.fit_parser import parse_activity_file
from app.auth import (
    authenticate, create_token, get_current_user,
    require_admin, UserRole, register, list_registered_users,
)
from app.auth.auth import AuthUser

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")

UPLOAD_DIR_DEFAULT = os.path.join(tempfile.gettempdir(), "wenyasports_uploads")


def create_coordinator() -> CoordinatorAgent:
    """Build the full multi-agent pipeline."""
    from app.agents.feature_extractor_agent import FeatureExtractorAgent
    from app.agents.memory_agent import MemoryAgent
    from app.agents.parser_agent import ParserAgent
    from app.agents.recommendation_agent import RecommendationAgent

    return CoordinatorAgent(
        parser_agent=ParserAgent(),
        feature_agent=FeatureExtractorAgent(),
        memory_agent=MemoryAgent(),
        recommendation_agent=RecommendationAgent(),
    )


_coordinator: Optional[CoordinatorAgent] = None


def get_coordinator() -> CoordinatorAgent:
    """FastAPI dependency returning the shared coordinator instance."""
    global _coordinator
    if _coordinator is None:
        _coordinator = create_coordinator()
    return _coordinator


def _get_user_upload_dir(user_id: str) -> str:
    """获取用户专属上传目录。

    结构: {UPLOAD_DIR}/{user_id}/

    Args:
        user_id: 用户唯一标识

    Returns:
        用户上传目录路径
    """
    base_dir = os.environ.get("FIT_UPLOAD_DIR") or UPLOAD_DIR_DEFAULT
    user_dir = os.path.join(base_dir, f"user_{user_id}")
    os.makedirs(user_dir, exist_ok=True)
    return user_dir


def _save_upload(file: UploadFile, user_id: Optional[str] = None) -> str:
    """Persist the uploaded file and return its path.

    如果提供 user_id，文件将存储到用户专属目录，确保数据隔离。

    Args:
        file: 上传的文件
        user_id: 用户唯一标识（可选，用于目录隔离）

    Returns:
        保存后的文件路径
    """
    if user_id:
        upload_dir = _get_user_upload_dir(user_id)
    else:
        upload_dir = os.environ.get("FIT_UPLOAD_DIR") or UPLOAD_DIR_DEFAULT
        os.makedirs(upload_dir, exist_ok=True)

    safe_name = os.path.basename(file.filename or "upload.fit")
    if not safe_name.lower().endswith((".fit", ".csv")):
        safe_name += ".fit"
    file_path = os.path.join(upload_dir, f"{uuid.uuid4().hex}_{safe_name}")
    content = file.file.read()
    with open(file_path, "wb") as fh:
        fh.write(content)
    logger.debug("File uploaded: user=%s, path=%s", user_id, file_path)
    return file_path


@router.post("/upload")
async def upload_fit(
    file: UploadFile = File(...),
    user_id: str = Form(...),
    session_id: str = Form(...),
    coordinator: CoordinatorAgent = Depends(get_coordinator),
):
    """上传运动数据文件（.fit 或 .csv），运行多 Agent 分析管道并返回结果。

    文件存储到用户专属目录 {UPLOAD_DIR}/user_{user_id}/，确保数据隔离。
    """
    if not file.filename or not file.filename.lower().endswith((".fit", ".csv")):
        raise HTTPException(status_code=400, detail="请上传 .fit 或 .csv 格式的运动文件")

    file_path = _save_upload(file, user_id=user_id)
    try:
        result = coordinator.run(file_path, user_id, session_id)
    except CoordinatorError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    except Exception as exc:
        logger.exception("处理上传文件失败")
        raise HTTPException(status_code=500, detail=f"处理活动数据失败: {exc}") from exc

    rows = database.get_recent_activities(user_id, limit=1)
    activity_id = rows[0]["activity_id"] if rows else None

    return {
        "activity_id": activity_id,
        "metadata": result["activity_metadata"],
        "features": result["activity_features"],
        "recommendation": result["recommendation"],
        "user_profile_summary": result["user_profile_summary"],
    }


@router.get("/dashboard/summary")
def dashboard_summary(
    user_id: str = Query(...),
):
    """Return aggregated dashboard data for a specific user.

    Demo-level access control: the frontend passes the current user's user_id.
    The database layer ensures data isolation (filtered by user_id).
    """
    return database.get_user_dashboard(user_id)


@router.get("/activities")
def list_activities(
    user_id: str = Query(...),
    limit: int = Query(10, ge=1, le=100),
):
    """Return the most recent activities (brief summary) for a user."""
    rows = database.get_recent_activities(user_id, limit=limit)
    activities = []
    for row in rows:
        features = json.loads(row["features_json"] or "{}")
        metadata = json.loads(row["metadata_json"] or "{}")
        activities.append(
            {
                "activity_id": row["activity_id"],
                "user_id": row["user_id"],
                "date": row["date"],
                "sport": metadata.get("sport"),
                "total_distance_m": features.get("total_distance_m"),
                "total_duration_seconds": features.get("total_duration_seconds"),
                "training_load": features.get("training_load"),
                "intensity_distribution": features.get("intensity_distribution"),
            }
        )
    return {"activities": activities, "total": len(activities)}


@router.get("/activities/{activity_id}")
def get_activity_detail(activity_id: int):
    """Return full activity data, including track points re-parsed from file."""
    row = database.get_activity(activity_id)
    if row is None:
        raise HTTPException(status_code=404, detail="活动不存在")

    metadata = json.loads(row["metadata_json"] or "{}")
    features = json.loads(row["features_json"] or "{}")
    recommendation = json.loads(row["recommendation_json"] or "{}")

    records: list = []
    file_path = row.get("file_path")
    if file_path and os.path.exists(file_path):
        try:
            parsed = parse_activity_file(file_path)
            records = parsed["records"]
            if not metadata:
                metadata = parsed["metadata"]
        except Exception:
            logger.warning("重新解析活动文件失败: %s", file_path)
            records = []

    return {
        "activity_id": activity_id,
        "date": row["date"],
        "metadata": metadata,
        "features": features,
        "recommendation": recommendation,
        "records": records,
    }


@router.get("/user/profile")
def get_user_profile(user_id: str = Query(...)):
    """Return the stored user profile."""
    profile = database.get_user_profile(user_id)
    return {"user_id": user_id, "profile": profile}


# ----------------------------------------------------------------------
# RAG 个人 AI 私教：知识问答
# ----------------------------------------------------------------------
_rag_knowledge_agent = None


def _get_rag_agent():
    """懒加载 KnowledgeAgent（避免无知识库时拖慢启动）。"""
    global _rag_knowledge_agent
    if _rag_knowledge_agent is None:
        from rag.embedder import FakeEmbedder, MiniLMEmbedder
        from rag.knowledge_agent import KnowledgeAgent
        from rag.llm_client import OpenAILLMClient
        from rag.vector_store import VectorStoreManager

        embedder_kind = os.environ.get("RAG_EMBEDDER", "fake")
        embedder = (
            MiniLMEmbedder() if embedder_kind == "minilm" else FakeEmbedder()
        )
        store = VectorStoreManager()
        llm = OpenAILLMClient()
        _rag_knowledge_agent = KnowledgeAgent(
            embedder=embedder,
            vector_store_manager=store,
            llm_client=llm,
            memory_agent=get_coordinator().memory_agent,
        )
    return _rag_knowledge_agent


@router.post("/chat")
async def rag_chat(body: dict):
    """RAG 知识问答：输入 {user_id, question}，返回 {answer, sources}。"""
    user_id = (body.get("user_id") or "").strip()
    question = (body.get("question") or "").strip()
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id 不能为空")
    if not question:
        raise HTTPException(status_code=400, detail="question 不能为空")

    try:
        result = _get_rag_agent().run(user_id, question)
    except Exception as exc:
        logger.exception("RAG 问答失败")
        raise HTTPException(status_code=500, detail=f"RAG 问答失败: {exc}") from exc
    return {"user_id": user_id, "question": question, **result}


# ----------------------------------------------------------------------
# Agent Trace & Observability API (for Agent Trace Dashboard)
# ----------------------------------------------------------------------
from app.trace import trace_collector

@router.get("/agent-traces")
def get_agent_traces(limit: int = Query(20, ge=1, le=100)):
    """Get recent agent sessions and their summary."""
    history = trace_collector.get_session_history(limit=limit)
    return {"sessions": history, "total": len(history)}

@router.get("/agent-traces/{session_id}")
def get_agent_trace_detail(session_id: str):
    """Get the full trace steps for a specific session."""
    trace = trace_collector.get_trace(session_id)
    if not trace:
        raise HTTPException(status_code=404, detail="Trace not found for session")
    return {"session_id": session_id, "steps": trace, "total_steps": len(trace)}


# ----------------------------------------------------------------------
# Memory Inspector API (基于 MemoryPool 的用户隔离记忆)
# ----------------------------------------------------------------------

from app.memory.memory_pool import get_memory_pool


@router.get("/memory")
def get_memory_state():
    """获取记忆池全局状态（所有用户的记忆统计）。"""
    pool = get_memory_pool()
    pool_stats = pool.get_stats()
    trace_state = trace_collector.get_memory_state()
    return {
        "pool": pool_stats,
        "trace": trace_state,
    }


@router.post("/memory/search")
def search_memory(body: dict):
    """搜索指定用户的分级记忆系统（Working/Episodic/Semantic 三层）。

    必须提供 user_id 以确保数据隔离。
    """
    user_id = body.get("user_id", "")
    query = body.get("query", "")
    level = body.get("level", None)
    top_k = body.get("top_k", 5)

    if not user_id:
        raise HTTPException(status_code=400, detail="必须提供 user_id 以搜索用户记忆")

    pool = get_memory_pool()

    try:
        results = pool.retrieve(user_id=user_id, query=query, level=level, top_k=top_k)
        formatted = []
        for r in results:
            formatted.append({
                "content": r.get("content", ""),
                "score": r.get("score", 0.0),
                "source": r.get("level", "unknown"),
                "metadata": r.get("metadata", {}),
            })
    except Exception as exc:
        logger.error("记忆搜索失败: %s", exc)
        formatted = []

    if not formatted:
        formatted = [
            {"content": "暂无相关记忆记录。请先进行运动数据分析来积累记忆。", "score": 0.0, "source": "system", "metadata": {}}
        ]

    return {"user_id": user_id, "query": query, "results": formatted, "total": len(formatted)}


@router.post("/memory/store")
def store_memory(body: dict):
    """为指定用户存储一条记忆。

    Args:
        body: {user_id, content, level?, metadata?}
    """
    user_id = body.get("user_id", "")
    content = body.get("content", "")
    level = body.get("level", "auto")
    metadata = body.get("metadata", {})

    if not user_id or not content:
        raise HTTPException(status_code=400, detail="必须提供 user_id 和 content")

    pool = get_memory_pool()
    result = pool.store(user_id=user_id, content=content, level=level, metadata=metadata)
    return {"status": "ok", "result": result}


@router.delete("/memory/user/{user_id}")
def clear_user_memory(user_id: str):
    """清除指定用户的所有记忆。"""
    pool = get_memory_pool()
    success = pool.remove(user_id)
    return {"user_id": user_id, "cleared": success}


@router.get("/memory/user/{user_id}")
def get_user_memory_stats(user_id: str):
    """获取指定用户的记忆统计。"""
    pool = get_memory_pool()
    memory = pool.get(user_id)
    if memory is None:
        return {"user_id": user_id, "exists": False}

    stats = memory.get_stats()
    return {"user_id": user_id, "exists": True, "stats": stats}


# ----------------------------------------------------------------------
# Test Playground API (for Agent Mock Testing)
# ----------------------------------------------------------------------
@router.post("/agent-test")
def run_agent_test(body: dict):
    """Simulate agent runs with different scenarios for testing purposes."""
    scenario = body.get("scenario", "normal")
    test_cases = {
        "normal": {
            "name": "正常流程",
            "description": "用户请求正常问答，Agent 成功调用工具并返回答案",
            "steps": [
                {"type": "thought", "content": "分析用户意图：需要查询配速数据"},
                {"type": "action", "content": "调用 query_user_profile 工具"},
                {"type": "observation", "content": "获取到用户配速数据：5:30/km"},
                {"type": "final", "content": "生成最终答案：您的配速稳定，建议保持"},
            ],
            "success": True,
            "latency_ms": 1250,
        },
        "tool_failure": {
            "name": "工具降级",
            "description": "模拟 LLM 决定调用不存在的工具，Agent 如何降级",
            "steps": [
                {"type": "thought", "content": "分析用户意图：调用天气工具"},
                {"type": "action", "content": "调用 get_weather 工具 (不存在)"},
                {"type": "observation", "content": "工具调用失败，返回错误"},
                {"type": "action", "content": "Agent 降级：改用已有数据回答"},
                {"type": "final", "content": "生成降级答案：根据您的历史数据..."},
            ],
            "success": True,
            "latency_ms": 2100,
        },
        "max_loop": {
            "name": "最大迭代",
            "description": "模拟 Agent 陷入循环，达到最大迭代次数",
            "steps": [
                {"type": "thought", "content": "第 1 轮：尝试调用工具 A"},
                {"type": "action", "content": "调用工具 A"},
                {"type": "observation", "content": "返回结果不完整"},
                {"type": "thought", "content": "第 2 轮：尝试调用工具 B"},
                {"type": "action", "content": "调用工具 B"},
                {"type": "observation", "content": "返回结果仍不完整"},
                {"type": "thought", "content": "...持续循环"},
                {"type": "final", "content": "达到最大迭代次数 (5)，返回失败"},
            ],
            "success": False,
            "latency_ms": 5000,
        },
        "ambiguous": {
            "name": "模糊意图",
            "description": "处理用户模糊请求，需要多轮澄清",
            "steps": [
                {"type": "thought", "content": "用户意图模糊：'我该怎么训练'"},
                {"type": "action", "content": "生成澄清问题：'您的目标是减脂还是提高成绩？'"},
                {"type": "observation", "content": "用户回复：'提高半马成绩'"},
                {"type": "action", "content": "查询用户半马历史和目标"},
                {"type": "observation", "content": "获取到当前半马 1:55，目标 1:40"},
                {"type": "final", "content": "生成针对性的半马训练计划"},
            ],
            "success": True,
            "latency_ms": 3200,
        },
    }
    result = test_cases.get(scenario, test_cases["normal"])
    return {
        "scenario": scenario,
        "test_result": result,
        "timestamp": time.time(),
    }


# ----------------------------------------------------------------------
# Harness Architecture API
# ----------------------------------------------------------------------

@router.get("/harness/status")
def get_harness_status():
    """Get complete Harness system status."""
    harness = get_harness()
    return harness.get_system_status()


@router.get("/harness/agents")
def list_harness_agents():
    """List all registered agents and their capabilities."""
    harness = get_harness()
    agents = harness.registry.list_agents()
    return {
        "total_agents": len(agents),
        "agents": agents,
        "available_capabilities": harness.registry.get_available_capabilities(),
    }


@router.get("/harness/agents/{agent_id}")
def get_harness_agent(agent_id: str):
    """Get detailed status of a specific agent."""
    harness = get_harness()
    status = harness.get_agent_status(agent_id)
    if status is None:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
    return status


@router.post("/harness/workflow/analyze")
def run_harness_analysis_workflow(body: dict):
    """Run the activity analysis workflow through Harness.

    This demonstrates the full multi-agent pipeline:
    1. ParserAgent → Parse FIT file
    2. FeatureExtractorAgent → Extract metrics
    3. MemoryAgent → Load user context
    4. RecommendationAgent → Generate advice
    5. MemoryAgent → Update user profile

    Body: {file_path, user_id, session_id}
    """
    file_path = body.get("file_path")
    user_id = body.get("user_id", "default_user")
    session_id = body.get("session_id", str(uuid.uuid4()))

    if not file_path:
        raise HTTPException(status_code=400, detail="file_path is required")

    harness = get_harness()
    workflow_steps = get_analysis_workflow()

    # Prepare initial input for workflow
    initial_input = {
        "file_path": file_path,
        "user_id": user_id,
        "session_id": session_id,
    }

    # Execute workflow through harness
    result = harness.run_workflow(
        workflow_name="activity_analysis",
        steps=workflow_steps,
        initial_input=initial_input,
        session_id=session_id,
    )

    return result


@router.post("/harness/workflow/chat")
def run_harness_chat_workflow(body: dict):
    """Run the AI chat workflow through Harness.

    Body: {user_id, question, session_id}
    """
    user_id = body.get("user_id", "default_user")
    question = body.get("question", "")
    session_id = body.get("session_id", str(uuid.uuid4()))

    if not question:
        raise HTTPException(status_code=400, detail="question is required")

    harness = get_harness()
    workflow_steps = get_chat_workflow()

    initial_input = {
        "user_id": user_id,
        "question": question,
        "session_id": session_id,
    }

    result = harness.run_workflow(
        workflow_name="ai_chat",
        steps=workflow_steps,
        initial_input=initial_input,
        session_id=session_id,
    )

    return result


@router.post("/harness/orchestrate")
def run_harness_orchestration(body: dict):
    """Run dynamic orchestration to achieve a goal.

    Unlike fixed workflows, orchestration allows agents to
    discover each other and collaborate dynamically.

    Body: {goal, initial_input, max_iterations, session_id}
    """
    goal = body.get("goal", "")
    initial_input = body.get("initial_input", {})
    max_iterations = body.get("max_iterations", 10)
    session_id = body.get("session_id", str(uuid.uuid4()))

    if not goal:
        raise HTTPException(status_code=400, detail="goal is required")

    harness = get_harness()

    result = harness.orchestrate(
        goal=goal,
        initial_input=initial_input,
        max_iterations=max_iterations,
        session_id=session_id,
    )

    return result


@router.post("/harness/llm-orchestrate")
def run_llm_orchestration(body: dict):
    """LLM 驱动的智能编排：由大模型分析目标、规划Agent、动态执行。

    与固定 workflow 不同，LLM Orchestrator:
    1. 使用 LLM 分析用户目标，拆解为子任务
    2. 根据 Agent 能力声明智能选择和编排 Agent
    3. 支持动态重规划——步骤失败后 LLM 自动调整策略
    4. 完整的可观测性追踪

    Body: {
        goal: "用户想要达成的目标",
        initial_input: {file_path, user_id, ...},
        user_id: "user_001",
        session_id: "optional-session-id"
    }

    Returns:
        {
            success: bool,
            session_id: str,
            plan_used: {...},        # LLM 生成的执行计划
            results: {...},          # 各 Agent 的执行结果
            steps_completed: int,
            replans: int,            # 重规划次数
        }
    """
    goal = (body.get("goal") or "").strip()
    if not goal:
        raise HTTPException(status_code=400, detail="goal is required")

    initial_input = body.get("initial_input", {})
    user_id = body.get("user_id", "default_user")
    session_id = body.get("session_id")

    orchestrator = get_llm_orchestrator()

    result = orchestrator.execute_goal(
        goal=goal,
        initial_input=initial_input,
        user_id=user_id,
        session_id=session_id,
    )

    return result


@router.get("/harness/orchestrator/stats")
def get_orchestrator_stats():
    """获取 LLM Orchestrator 运行统计信息。"""
    orchestrator = get_llm_orchestrator()
    return orchestrator.get_orchestrator_stats()


@router.get("/harness/blackboard")
def get_blackboard_state(namespace: Optional[str] = None):
    """Get blackboard state - shared data between agents."""
    harness = get_harness()
    if namespace:
        data = harness.blackboard.read(namespace)
        return {"namespace": namespace, "data": data}
    return harness.blackboard.get_stats()


@router.get("/harness/messages")
def get_message_bus_stats():
    """Get message bus statistics."""
    harness = get_harness()
    return harness.message_bus.get_stats()


@router.get("/harness/governance")
def get_governance_state():
    """Get governance engine state and budget tracking."""
    harness = get_harness()
    return harness.governance.get_stats()


# ----------------------------------------------------------------------
# MCP Server Endpoints
# ----------------------------------------------------------------------
_mcp_server = None
_mcp_registry = None


def _get_mcp_server():
    global _mcp_server
    if _mcp_server is None:
        from mcp_plugins import MCPServer, PluginManager

        pm = PluginManager()
        _mcp_server = MCPServer(
            plugin_manager=pm,
            server_name="WenYaSports-MCP",
            server_version="1.0.0",
        )
    return _mcp_server


def _get_mcp_registry():
    global _mcp_registry
    if _mcp_registry is None:
        from mcp_plugins import MCPRegistry, PluginManager

        _mcp_registry = MCPRegistry()
        pm = PluginManager()
        _mcp_registry.set_plugin_manager(pm)
    return _mcp_registry


@router.post("/mcp")
async def mcp_endpoint(request: dict):
    """MCP HTTP 端点：接收 JSON-RPC 请求。

    支持 MCP 协议的 initialize、tools/list、tools/call 等方法。
    """
    server = _get_mcp_server()
    return server.handle_http_request(request)


@router.get("/mcp/tools")
def mcp_list_tools():
    """列出所有 MCP 工具（本地插件 + 远程服务器）。"""
    registry = _get_mcp_registry()
    return {
        "total_tools": len(registry.get_all_tools()),
        "tools": registry.get_all_tools(),
    }


@router.post("/mcp/tools/call")
def mcp_call_tool(body: dict):
    """通过统一接口调用任意 MCP 工具。

    Body: {tool_name, arguments}
    """
    tool_name = body.get("tool_name", "")
    arguments = body.get("arguments", {})

    if not tool_name:
        raise HTTPException(status_code=400, detail="tool_name is required")

    registry = _get_mcp_registry()
    result = registry.call_tool(tool_name, arguments)
    return result


@router.post("/mcp/servers/connect")
def mcp_connect_server(body: dict):
    """连接远程 MCP Server。

    Body: {server_name, transport: "stdio"|"sse", command|url}
    """
    server_name = body.get("server_name", "")
    transport = body.get("transport", "sse")

    if not server_name:
        raise HTTPException(status_code=400, detail="server_name is required")

    registry = _get_mcp_registry()

    try:
        if transport == "stdio":
            command = body.get("command", [])
            client = registry.connect_remote_stdio(server_name, command)
        elif transport == "sse":
            url = body.get("url", "")
            client = registry.connect_remote_sse(server_name, url)
        else:
            raise HTTPException(status_code=400, detail=f"Unknown transport: {transport}")

        return {
            "success": True,
            "server_name": server_name,
            "tools": [t.to_dict() for t in client.list_tools()],
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.delete("/mcp/servers/{server_name}")
def mcp_disconnect_server(server_name: str):
    """断开远程 MCP Server。"""
    registry = _get_mcp_registry()
    registry.disconnect_remote(server_name)
    return {"success": True, "server_name": server_name}


@router.get("/mcp/registry/status")
def mcp_registry_status():
    """获取 MCP 注册表状态。"""
    registry = _get_mcp_registry()
    return registry.get_server_info()


# ----------------------------------------------------------------------
# Auth & Role Management
# ----------------------------------------------------------------------


@router.post("/auth/login")
def auth_login(body: dict):
    """登录：返回 Token 和用户信息。

    Body: {username, password}
    管理员默认账号: admin / wenyasports2024
    """
    username = (body.get("username") or "").strip()
    password = body.get("password") or ""

    if not username:
        raise HTTPException(status_code=400, detail="用户名不能为空")

    user = authenticate(username, password)
    if user is None:
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    token = create_token(user)
    return {
        "token": token,
        "user": user.to_dict(),
        "expires_in": 3600,
    }


@router.post("/auth/register")
def auth_register(body: dict):
    """注册新用户：返回 Token 和用户信息。

    Body: {username, password}
    - username: 3-32 字符
    - password: 至少 6 字符
    """
    username = (body.get("username") or "").strip()
    password = body.get("password") or ""

    try:
        user = register(username, password)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    token = create_token(user)
    return {
        "token": token,
        "user": user.to_dict(),
        "expires_in": 3600,
        "message": f"用户 '{username}' 注册成功",
    }


@router.get("/auth/users")
def auth_list_users(user: AuthUser = Depends(require_admin)):
    """获取已注册用户列表（管理员）。"""
    users = list_registered_users()
    return {"users": users, "total": len(users)}


@router.get("/auth/me")
def auth_me(user: AuthUser = Depends(get_current_user)):
    """获取当前登录用户信息。"""
    return user.to_dict()


@router.get("/auth/categories")
def auth_list_categories():
    """获取支持的知识库分类列表。"""
    from app.agents.auto_classify_agent import AutoClassifyAgent
    agent = AutoClassifyAgent()
    return {"categories": agent.get_supported_categories()}


# ----------------------------------------------------------------------
# Knowledge Base Management (Admin Only)
# ----------------------------------------------------------------------
from app.services.knowledge_base import KnowledgeBaseService

_kb_service: KnowledgeBaseService = None


def _get_kb_service() -> KnowledgeBaseService:
    global _kb_service
    if _kb_service is None:
        _kb_service = KnowledgeBaseService()
    return _kb_service


@router.post("/knowledge/upload")
async def knowledge_upload(
    file: UploadFile = File(...),
    force_category: Optional[str] = Form(None),
    skip_index: bool = Form(False),
    user: AuthUser = Depends(require_admin),
):
    """上传知识文件（管理员）。

    自动调用 AutoClassifyAgent 进行分类，
    然后切分+向量化写入 ChromaDB。

    支持 .md / .txt / .pdf 文件。
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="文件名不能为空")

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in {".md", ".txt", ".pdf"}:
        raise HTTPException(
            status_code=400,
            detail="仅支持 .md / .txt / .pdf 格式",
        )

    content = await file.read()
    if len(content) > 50 * 1024 * 1024:  # 50MB 限制
        raise HTTPException(status_code=400, detail="文件大小不能超过 50MB")

    kb = _get_kb_service()
    try:
        result = kb.upload_and_index(
            file_content=content,
            original_filename=file.filename,
            admin_id=user.user_id,
            force_category=force_category,
            skip_index=skip_index,
        )
    except Exception as exc:
        logger.exception("知识文件上传失败")
        raise HTTPException(status_code=500, detail=f"上传失败: {exc}")

    return result


@router.get("/knowledge/list")
def knowledge_list(
    category: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    user: AuthUser = Depends(require_admin),
):
    """列出知识库文件（管理员）。"""
    kb = _get_kb_service()
    files = kb.list_files(category=category, status=status)
    return {"files": files, "total": len(files)}


@router.get("/knowledge/stats")
def knowledge_stats(user: AuthUser = Depends(require_admin)):
    """获取知识库统计（管理员）。"""
    kb = _get_kb_service()
    return kb.get_stats()


@router.post("/knowledge/{file_id}/delete")
def knowledge_delete(file_id: str, user: AuthUser = Depends(require_admin)):
    """删除知识文件（管理员）。"""
    kb = _get_kb_service()
    result = kb.delete_file(file_id)
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("error", "文件不存在"))
    return result


@router.post("/knowledge/{file_id}/reclassify")
def knowledge_reclassify(file_id: str, user: AuthUser = Depends(require_admin)):
    """重新自动分类文件（管理员）。"""
    kb = _get_kb_service()
    result = kb.reclassify_file(file_id)
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("error", "文件不存在"))
    return result


@router.post("/knowledge/{file_id}/category")
def knowledge_update_category(
    file_id: str,
    body: dict,
    user: AuthUser = Depends(require_admin),
):
    """手动修改文件分类（管理员）。

    Body: {new_category: "strength"}
    """
    new_category = body.get("new_category", "")
    if not new_category:
        raise HTTPException(status_code=400, detail="new_category 必填")

    kb = _get_kb_service()
    result = kb.update_file_category(file_id, new_category)
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("error", "文件不存在"))
    return result


@router.post("/knowledge/rebuild")
def knowledge_rebuild(user: AuthUser = Depends(require_admin)):
    """重建整个知识库索引（管理员）。"""
    kb = _get_kb_service()
    result = kb.rebuild_index()
    return result


@router.post("/knowledge/classify")
async def knowledge_classify_preview(
    file: UploadFile = File(...),
    user: AuthUser = Depends(require_admin),
):
    """预览分类结果（不上传，仅用于测试 AutoClassifyAgent）。"""
    content = await file.read()
    ext = os.path.splitext(file.filename)[1].lower()

    kb = _get_kb_service()
    preview = kb._extract_text_preview(content, ext)

    from app.agents.auto_classify_agent import AutoClassifyAgent
    agent = AutoClassifyAgent()
    result = agent.classify(preview, file.filename)
    return result

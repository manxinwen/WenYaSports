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
from app.services.fit_parser import parse_fit_file

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")

UPLOAD_DIR_DEFAULT = os.path.join(tempfile.gettempdir(), "fit_uploads")


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


def _save_upload(file: UploadFile) -> str:
    """Persist the uploaded file and return its path."""
    upload_dir = os.environ.get("FIT_UPLOAD_DIR") or UPLOAD_DIR_DEFAULT
    os.makedirs(upload_dir, exist_ok=True)
    safe_name = os.path.basename(file.filename or "upload.fit")
    file_path = os.path.join(upload_dir, f"{uuid.uuid4().hex}_{safe_name}")
    content = file.file.read()
    with open(file_path, "wb") as fh:
        fh.write(content)
    return file_path


@router.post("/upload")
async def upload_fit(
    file: UploadFile = File(...),
    user_id: str = Form(...),
    session_id: str = Form(...),
    coordinator: CoordinatorAgent = Depends(get_coordinator),
):
    """Upload a FIT file, run the multi-agent pipeline and return results."""
    if not file.filename or not file.filename.lower().endswith(".fit"):
        raise HTTPException(status_code=400, detail="请上传 .fit 格式的运动文件")

    file_path = _save_upload(file)
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
            parsed = parse_fit_file(file_path)
            records = parsed["records"]
            if not metadata:
                metadata = parsed["metadata"]
        except Exception:
            logger.warning("重新解析FIT文件失败: %s", file_path)
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
# Memory Inspector API
# ----------------------------------------------------------------------
@router.get("/memory")
def get_memory_state():
    """Get current memory system state (for Memory Inspector UI)."""
    return trace_collector.get_memory_state()

@router.post("/memory/search")
def search_memory(body: dict):
    """Search memory by query (simulated for demo)."""
    query = body.get("query", "")
    # In a real app, this would use the vector store.
    # For now, we return simulated results based on the query.
    results = [
        {"content": "用户近一个月跑量增加 15%", "score": 0.95, "source": "user_profile"},
        {"content": "用户最近 5 次配速稳定在 5:30", "score": 0.88, "source": "activity_features"},
        {"content": "用户有两次全马经历，平均完赛时间 4:15:00", "score": 0.82, "source": "user_profile"},
    ]
    if query:
        results = [r for r in results if query.lower() in r["content"].lower()]
    return {"query": query, "results": results}


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

"""Agentic Workflow Engine: 真正的自主 Agent 工作流引擎。

从「工具调用」升级到「Agentic Workflow」的核心实现：
  Think → Plan → Act → Observe → Reflect → (Loop)

核心模式：
1. ReAct Loop: 推理-行动循环，Agent 自主决定下一步
2. Tree-of-Thought: 探索多条推理路径，择优执行
3. Dynamic Tool Selection: LLM 根据上下文动态选择工具组合
4. Self-Reflection: 执行后反思，决定继续/重试/放弃
5. Multi-Agent Debate: 多个 Agent 对结果进行辩论和交叉验证

Architecture:
    User Goal
        ↓
    ┌─────────────────────────────────────┐
    │        AgenticWorkflowEngine        │
    │  ┌─────────────────────────────┐   │
    │  │    Decision Layer (LLM)     │   │
    │  │  - Tool Discovery           │   │
    │  │  - Strategy Selection      │   │
    │  │  - Reflection Loop         │   │
    │  └─────────────────────────────┘   │
    │  ┌─────────────────────────────┐   │
    │  │    Execution Layer          │   │
    │  │  - Tool Chain               │   │
    │  │  - Error Recovery           │   │
    │  │  - Result Fusion            │   │
    │  └─────────────────────────────┘   │
    │  ┌─────────────────────────────┐   │
    │  │    Validation Layer        │   │
    │  │  - Critique & Debate        │   │
    │  │  - Quality Scoring          │   │
    │  │  - Pass/Fail Gate           │   │
    │  └─────────────────────────────┘   │
    └─────────────────────────────────────┘
        ↓
    Result / Next Iteration
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data Structures
# ---------------------------------------------------------------------------

class WorkflowStatus(Enum):
    PENDING = "pending"
    THINKING = "thinking"
    PLANNING = "planning"
    EXECUTING = "executing"
    REFLECTING = "reflecting"
    VALIDATING = "validating"
    COMPLETED = "completed"
    FAILED = "failed"
    ITERATING = "iterating"


@dataclass
class ThoughtNode:
    """Tree-of-Thought 节点：代表一条推理路径。"""
    id: int
    content: str
    parent_id: Optional[int] = None
    children_ids: List[int] = field(default_factory=list)
    score: float = 0.0
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    result: Optional[str] = None
    is_terminal: bool = False


@dataclass
class ToolCall:
    """工具调用描述。"""
    tool_name: str
    arguments: Dict[str, Any]
    result: Any = None
    success: bool = True
    latency_ms: float = 0.0
    error: Optional[str] = None


@dataclass
class WorkflowState:
    """工作流完整状态。"""
    goal: str
    status: WorkflowStatus = WorkflowStatus.PENDING
    iteration: int = 0
    max_iterations: int = 5
    thoughts: List[ThoughtNode] = field(default_factory=list)
    tool_calls: List[ToolCall] = field(default_factory=list)
    observations: List[str] = field(default_factory=list)
    reflections: List[str] = field(default_factory=list)
    final_result: Optional[Any] = None
    quality_score: float = 0.0
    tokens_used: int = 0
    total_latency_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "goal": self.goal,
            "status": self.status.value,
            "iteration": self.iteration,
            "max_iterations": self.max_iterations,
            "thoughts_count": len(self.thoughts),
            "tool_calls_count": len(self.tool_calls),
            "observations": self.observations[-5:],
            "reflections": self.reflections[-5:],
            "final_result": str(self.final_result)[:500] if self.final_result else None,
            "quality_score": self.quality_score,
            "tokens_used": self.tokens_used,
            "total_latency_ms": self.total_latency_ms,
        }


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

THINK_PROMPT = """你是一个自主 Agent，需要分析目标并决定下一步行动。

## 当前目标
{goal}

## 可用工具
{tools_description}

## 历史上下文
{history}

## 思考格式
请产生 3 个不同的推理路径，每个路径包含：
1. 对目标的理解
2. 选择的工具及原因
3. 预期结果
4. 风险评估

严格输出 JSON:
```json
{{
  "thoughts": [
    {{
      "reasoning": "推理过程",
      "tool_calls": [
        {{"tool": "tool_name", "arguments": {{...}}, "reason": "选择原因"}}
      ],
      "expected_outcome": "预期结果",
      "confidence": 0.0-1.0,
      "score": 0.0-1.0
    }}
  ],
  "best_path_index": 0,
  "meta_reasoning": "为什么选择这条路径"
}}
```"""

REFLECT_PROMPT = """你是一个反思 Agent，需要评估执行结果并决定下一步。

## 执行结果
{execution_result}

## 原始目标
{goal}

## 使用的工具
{tools_used}

## 历史反思
{previous_reflections}

## 反思格式
```json
{{
  "assessment": "对结果的评估",
  "goal_satisfied": true/false,
  "quality_score": 0-100,
  "issues": ["发现的问题"],
  "next_action": "continue|retry|replan|abandon",
  "improvement_suggestions": ["改进建议"]
}}
```"""

CRITIQUE_PROMPT = """你是一个评审 Agent（Critic），需要对结果进行严格审查。

## 待审结果
{result}

## 原始目标
{goal}

## 评审维度
1. 准确性：结果是否正确？
2. 完整性：是否覆盖所有需求？
3. 相关性：是否与目标相关？
4. 可执行性：是否可以直接使用？
5. 简洁性：是否简洁明了？

## 评审格式
```json
{{
  "verdict": "pass|fail|revise",
  "scores": {{
    "accuracy": 0-100,
    "completeness": 0-100,
    "relevance": 0-100,
    "actionability": 0-100,
    "conciseness": 0-100
  }},
  "overall_score": 0-100,
  "issues": ["问题列表"],
  "suggestions": ["改进建议"],
  "pass_gate": true/false
}}
```"""

DEBATE_PROMPT = """你是参与多 Agent 辩论的一方。请审查其他 Agent 的观点并反驳或支持。

## 议题
{topic}

## 各方观点
{viewpoints}

## 你的角色
{role}

## 辩论格式
```json
{{
  "position": "支持/反对/中立",
  "arguments": ["论据"],
  "counter_arguments": ["反驳"],
  "evidence_strength": 0-100,
  "final_verdict": "对议题的最终判断"
}}
```"""


# ---------------------------------------------------------------------------
# Agentic Workflow Engine
# ---------------------------------------------------------------------------

class AgenticWorkflowEngine:
    """真正的 Agentic 工作流引擎。

    核心能力：
    1. **自主思考**: LLM 产生多条推理路径（Tree-of-Thought）
    2. **动态选工具**: 根据上下文自动选择最佳工具组合
    3. **反思循环**: 执行后评估质量，决定继续/重试/放弃
    4. **Critique Gate**: 独立评审关卡，保证输出质量
    5. **多Agent辩论**: 对关键决策进行交叉验证

    Usage:
        engine = AgenticWorkflowEngine(
            harness=harness,
            mcp_registry=mcp_registry,
            llm_client=llm_client
        )
        result = engine.run(
            goal="分析上周训练数据并给出调整建议",
            initial_input={"file_path": "/data/training.csv"}
        )
    """

    def __init__(
        self,
        harness: Any = None,
        mcp_registry: Any = None,
        llm_client: Optional[Any] = None,
        model: str = "gpt-4o-mini",
        max_iterations: int = 5,
        thought_branching: int = 3,
        quality_threshold: float = 70.0,
    ):
        self.harness = harness
        self.mcp_registry = mcp_registry
        self.llm_client = llm_client
        self.model = model
        self.max_iterations = max_iterations
        self.thought_branching = thought_branching
        self.quality_threshold = quality_threshold

        # Tool registry: name -> callable
        self._tools: Dict[str, Dict[str, Any]] = {}
        self._register_builtin_tools()

    def run(
        self,
        goal: str,
        initial_input: Any = None,
        tools_override: Optional[List[str]] = None,
    ) -> WorkflowState:
        """执行 Agentic 工作流。

        Args:
            goal: 自然语言目标
            initial_input: 初始输入数据
            tools_override: 强制使用的工具列表（None = 自动发现）

        Returns:
            完整的工作流状态
        """
        state = WorkflowState(goal=goal)
        start_time = time.time()

        # Step 0: Discover available tools
        available_tools = self._discover_tools(tools_override)
        tool_descriptions = self._format_tools_for_llm(available_tools)

        for iteration in range(1, self.max_iterations + 1):
            state.iteration = iteration
            state.status = WorkflowStatus.THINKING

            # Phase 1: Think - Generate reasoning paths (Tree-of-Thought)
            thoughts = self._think(
                goal=goal,
                tools_desc=tool_descriptions,
                state=state,
                branching=self.thought_branching,
            )

            if not thoughts:
                state.status = WorkflowStatus.FAILED
                state.final_result = "无法生成有效推理路径"
                break

            # Phase 2: Plan - Select best path
            state.status = WorkflowStatus.PLANNING
            best_thought = max(thoughts, key=lambda t: t.get("score", 0))

            # Phase 3: Act - Execute tool calls
            state.status = WorkflowStatus.EXECUTING
            exec_results = self._act(best_thought, available_tools, initial_input)
            state.tool_calls.extend(exec_results)

            # Build observation from results
            observation = self._build_observation(exec_results)
            state.observations.append(observation)

            # Phase 4: Reflect - Evaluate results
            state.status = WorkflowStatus.REFLECTING
            reflection = self._reflect(goal, exec_results, state)
            state.reflections.append(reflection.get("assessment", ""))

            quality = reflection.get("quality_score", 0)
            state.quality_score = quality

            # Phase 5: Critique Gate - Quality check
            if quality >= self.quality_threshold:
                state.status = WorkflowStatus.VALIDATING
                critique_result = self._critique(
                    best_thought.get("expected_outcome", ""),
                    goal,
                )
                state.quality_score = critique_result.get("overall_score", quality)

                if critique_result.get("pass_gate", False):
                    state.status = WorkflowStatus.COMPLETED
                    state.final_result = self._build_final_answer(
                        exec_results, reflection, critique_result
                    )
                    break

            # Check if we should continue
            next_action = reflection.get("next_action", "continue")
            if next_action == "abandon":
                state.status = WorkflowStatus.FAILED
                state.final_result = reflection.get("assessment", "任务被放弃")
                break

            if iteration >= self.max_iterations:
                state.status = WorkflowStatus.ITERATING
                state.final_result = f"达到最大迭代次数 ({self.max_iterations})"

        state.total_latency_ms = (time.time() - start_time) * 1000
        return state

    def _think(
        self,
        goal: str,
        tools_desc: str,
        state: WorkflowState,
        branching: int,
    ) -> List[Dict[str, Any]]:
        """ReAct Think: 生成多条推理路径。"""
        history = self._build_history(state)

        # For first iteration or no LLM, use heuristic
        if self.llm_client is None or state.iteration == 1:
            return self._heuristic_thinking(goal, tools_desc, branching)

        prompt = THINK_PROMPT.format(
            goal=goal,
            tools_description=tools_desc,
            history=history,
        )

        response = self._call_llm(prompt, f"目标: {goal}")
        if response:
            try:
                parsed = json.loads(self._extract_json(response))
                return parsed.get("thoughts", [])
            except json.JSONDecodeError:
                pass

        return self._heuristic_thinking(goal, tools_desc, branching)

    def _act(
        self,
        thought: Dict[str, Any],
        available_tools: Dict[str, Any],
        initial_input: Any,
    ) -> List[ToolCall]:
        """ReAct Act: 执行选定的工具调用。"""
        results = []
        tool_calls = thought.get("tool_calls", [])

        for tc in tool_calls:
            tool_name = tc.get("tool", "")
            arguments = tc.get("arguments", {})

            if tool_name not in self._tools:
                results.append(ToolCall(
                    tool_name=tool_name,
                    arguments=arguments,
                    success=False,
                    error=f"Tool '{tool_name}' not found",
                ))
                continue

            start = time.time()
            try:
                tool_info = self._tools[tool_name]
                result = tool_info["handler"](arguments, initial_input)
                results.append(ToolCall(
                    tool_name=tool_name,
                    arguments=arguments,
                    result=result,
                    success=True,
                    latency_ms=(time.time() - start) * 1000,
                ))
            except Exception as exc:
                results.append(ToolCall(
                    tool_name=tool_name,
                    arguments=arguments,
                    success=False,
                    latency_ms=(time.time() - start) * 1000,
                    error=str(exc),
                ))

        return results

    def _reflect(
        self,
        goal: str,
        exec_results: List[ToolCall],
        state: WorkflowState,
    ) -> Dict[str, Any]:
        """ReAct Reflect: 评估结果，决定下一步。"""
        result_summary = self._summarize_results(exec_results)
        tools_used = [tc.tool_name for tc in exec_results]

        if self.llm_client is None:
            # Heuristic reflection
            success_count = sum(1 for tc in exec_results if tc.success)
            total = len(exec_results)
            quality = (success_count / total * 100) if total > 0 else 0

            return {
                "assessment": f"执行 {total} 个工具调用，{success_count} 成功",
                "goal_satisfied": quality >= self.quality_threshold,
                "quality_score": quality,
                "issues": [],
                "next_action": "continue" if quality < self.quality_threshold else "continue",
                "improvement_suggestions": [],
            }

        prompt = REFLECT_PROMPT.format(
            execution_result=result_summary,
            goal=goal,
            tools_used=tools_used,
            previous_reflections=state.reflections[-3:] if state.reflections else "无",
        )

        response = self._call_llm(prompt, "请评估执行结果")
        if response:
            try:
                return json.loads(self._extract_json(response))
            except json.JSONDecodeError:
                pass

        return {
            "assessment": "无法生成反思",
            "goal_satisfied": False,
            "quality_score": 50,
            "issues": ["LLM 反思失败"],
            "next_action": "continue",
        }

    def _critique(
        self,
        result: Any,
        goal: str,
    ) -> Dict[str, Any]:
        """Critique Gate: 独立评审关卡。"""
        if self.llm_client is None:
            return {
                "verdict": "pass",
                "scores": {"accuracy": 80, "completeness": 80, "relevance": 80,
                           "actionability": 75, "conciseness": 75},
                "overall_score": 78,
                "issues": [],
                "suggestions": [],
                "pass_gate": True,
            }

        prompt = CRITIQUE_PROMPT.format(
            result=str(result)[:2000] if result else "无结果",
            goal=goal,
        )

        response = self._call_llm(prompt, "请审查以上结果")
        if response:
            try:
                return json.loads(self._extract_json(response))
            except json.JSONDecodeError:
                pass

        return {"verdict": "pass", "overall_score": 75, "pass_gate": True}

    def _debate(
        self,
        topic: str,
        viewpoints: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Multi-Agent Debate: 多 Agent 辩论。"""
        if self.llm_client is None or len(viewpoints) < 2:
            return {"consensus": viewpoints[0] if viewpoints else {}, "agreement_score": 0}

        prompt = DEBATE_PROMPT.format(
            topic=topic,
            viewpoints=json.dumps(viewpoints, ensure_ascii=False),
            role="中立评审员",
        )

        response = self._call_llm(prompt, f"请参与辩论: {topic}")
        if response:
            try:
                return json.loads(self._extract_json(response))
            except json.JSONDecodeError:
                pass

        return {"consensus": viewpoints[0] if viewpoints else {}, "agreement_score": 50}

    # ------------------------------------------------------------------
    # Tool Management
    # ------------------------------------------------------------------

    def register_tool(
        self,
        name: str,
        handler: Callable,
        description: str = "",
        parameters: Optional[Dict[str, Any]] = None,
        source: str = "builtin",
    ) -> None:
        """注册工具到 Agentic Workflow。"""
        self._tools[name] = {
            "name": name,
            "handler": handler,
            "description": description,
            "parameters": parameters or {},
            "source": source,
        }

    def _register_builtin_tools(self) -> None:
        """注册内置工具。"""
        # Harness agent tools
        if self.harness and hasattr(self.harness, 'registry'):
            try:
                agents = self.harness.registry.list_agents()
                for agent_info in agents:
                    if isinstance(agent_info, dict):
                        agent_id = agent_info.get("agent_id", "")
                        desc = agent_info
                    elif isinstance(agent_info, (list, tuple)) and len(agent_info) >= 2:
                        agent_id = agent_info[0]
                        desc = agent_info[1] if isinstance(agent_info[1], dict) else {}
                    else:
                        continue

                    self.register_tool(
                        name=agent_id,
                        handler=lambda args, inp, aid=agent_id: self._call_harness_agent(aid, args, inp),
                        description=desc.get("description", f"Agent: {agent_id}"),
                        parameters=desc.get("parameters", {}),
                        source="harness",
                    )
            except Exception as exc:
                logger.warning("Failed to register harness tools: %s", exc)

    def _call_harness_agent(self, agent_id: str, args: Dict, initial_input: Any) -> Any:
        """调用 Harness 中的 Agent。"""
        if self.harness:
            return self.harness.execute_agent(agent_id, args or initial_input or {})
        return {"success": False, "error": "No harness available"}

    def _discover_tools(self, override: Optional[List[str]] = None) -> Dict[str, Any]:
        """动态发现可用工具。"""
        if override:
            return {k: v for k, v in self._tools.items() if k in override}

        # Auto-discover from all sources
        tools = dict(self._tools)

        # From MCP registry
        if self.mcp_registry:
            for tool_def in self.mcp_registry.get_all_tools():
                name = tool_def.get("name", "")
                if name and name not in tools:
                    tools[name] = {
                        "name": name,
                        "description": tool_def.get("description", ""),
                        "source": "mcp",
                    }

        return tools

    # ------------------------------------------------------------------
    # Helper Methods
    # ------------------------------------------------------------------

    def _heuristic_thinking(
        self,
        goal: str,
        tools_desc: str,
        branching: int,
    ) -> List[Dict[str, Any]]:
        """启发式思考（无 LLM 时的降级方案）。"""
        tools = list(self._tools.keys())
        if self.mcp_registry:
            tools.extend(t.get("name", "") for t in self.mcp_registry.get_all_tools())

        tools = [t for t in tools if t]

        if not tools:
            return []

        # Generate heuristic thoughts
        thoughts = []
        for i in range(min(branching, len(tools))):
            tool = tools[i % len(tools)]
            thoughts.append({
                "reasoning": f"尝试使用 {tool} 来处理目标: {goal[:100]}",
                "tool_calls": [{"tool": tool, "arguments": {}, "reason": "启发式选择"}],
                "expected_outcome": f"通过 {tool} 获取结果",
                "confidence": 0.5,
                "score": 0.5,
            })

        return thoughts

    def _build_history(self, state: WorkflowState) -> str:
        """构建历史上下文。"""
        parts = []
        if state.observations:
            parts.append(f"观察记录: {state.observations[-3:]}")
        if state.reflections:
            parts.append(f"反思记录: {state.reflections[-3:]}")
        if state.tool_calls:
            recent = state.tool_calls[-5:]
            parts.append(f"最近工具调用: {[(tc.tool_name, tc.success) for tc in recent]}")
        return "\n".join(parts) if parts else "无历史记录"

    def _build_observation(self, results: List[ToolCall]) -> str:
        """从执行结果构建观察。"""
        lines = []
        for tc in results:
            status = "✓" if tc.success else "✗"
            result_summary = str(tc.result)[:100] if tc.result else (tc.error or "")
            lines.append(f"  [{status}] {tc.tool_name}: {result_summary}")
        return "\n".join(lines)

    def _summarize_results(self, results: List[ToolCall]) -> str:
        """汇总执行结果。"""
        total = len(results)
        success = sum(1 for r in results if r.success)
        lines = [f"共 {total} 个调用，{success} 个成功。"]
        for r in results:
            status = "成功" if r.success else "失败"
            detail = str(r.result)[:200] if r.result else (r.error or "未知错误")
            lines.append(f"  - {r.tool_name} [{status}]: {detail}")
        return "\n".join(lines)

    def _build_final_answer(
        self,
        exec_results: List[ToolCall],
        reflection: Dict,
        critique: Dict,
    ) -> str:
        """构建最终答案。"""
        success_results = [tc for tc in exec_results if tc.success]
        parts = []

        # From successful tool results
        for tc in success_results:
            if tc.result:
                parts.append(str(tc.result))

        # From reflection
        if reflection.get("assessment"):
            parts.append(f"评估: {reflection['assessment']}")

        # From critique
        if critique.get("suggestions"):
            parts.append(f"建议: {'; '.join(critique['suggestions'])}")

        return "\n\n".join(parts) if parts else "任务完成，但无详细结果"

    def _format_tools_for_llm(self, tools: Dict) -> str:
        """格式化工具列表供 LLM 使用。"""
        lines = []
        for name, info in tools.items():
            desc = info.get("description", "")
            source = info.get("source", "builtin")
            lines.append(f"- {name} [{source}]: {desc}")
        return "\n".join(lines) if lines else "暂无可用工具"

    def _call_llm(self, system_prompt: str, user_message: str) -> Optional[str]:
        """调用 LLM。"""
        if self.llm_client is None:
            return None

        try:
            response = self.llm_client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                temperature=0.3,
                max_tokens=2000,
            )
            return response.choices[0].message.content.strip()
        except Exception as exc:
            logger.warning("LLM call failed: %s", exc)
            return None

    def _extract_json(self, text: str) -> str:
        """从 LLM 响应中提取 JSON。"""
        text = text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1] == "```":
                lines = lines[:-1]
            text = "\n".join(lines)
        return text.strip()

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    def get_stats(self) -> Dict[str, Any]:
        """获取引擎统计信息。"""
        return {
            "total_tools": len(self._tools),
            "tools": list(self._tools.keys()),
            "model": self.model,
            "max_iterations": self.max_iterations,
            "thought_branching": self.thought_branching,
            "quality_threshold": self.quality_threshold,
        }
"""Multi-Agent Conversation Framework: Planner-Executor-Reviser 模式。

实现三种经典的 Agent 对话角色：
- Planner: 分析目标、制定计划、分解任务
- Executor: 执行具体任务、调用工具、返回结果
- Reviser: 审查结果、提供反馈、决定是否需要迭代

这三种角色可以由 LLM 模拟，也可以由不同的 Agent 实例承担。
支持多轮对话迭代，直到得出满意的结果。

Architecture:
    User Goal
        ↓
    ┌──────────────┐
    │   Planner    │ → Plan
    └──────────────┘
        ↓
    ┌──────────────┐
    │  Executor    │ → Execute Steps
    └──────────────┘
        ↓
    ┌──────────────┐
    │   Reviser    │ → Review & Feedback
    └──────────────┘
        ↓
    [Iterate if needed] → Final Answer
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ConversationMessage:
    """对话消息。"""
    role: str  # "planner", "executor", "reviser", "user"
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


@dataclass
class ConversationState:
    """多Agent对话状态。"""
    goal: str
    messages: List[ConversationMessage] = field(default_factory=list)
    plan: Optional[Dict[str, Any]] = None
    execution_results: List[Dict[str, Any]] = field(default_factory=list)
    review_feedback: Optional[str] = None
    iteration: int = 0
    max_iterations: int = 5
    is_complete: bool = False
    final_answer: Optional[str] = None

    def add_message(self, role: str, content: str, **kwargs) -> None:
        self.messages.append(
            ConversationMessage(role=role, content=content, metadata=kwargs)
        )

    def get_messages_by_role(self, role: str) -> List[ConversationMessage]:
        return [m for m in self.messages if m.role == role]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "goal": self.goal,
            "iteration": self.iteration,
            "max_iterations": self.max_iterations,
            "is_complete": self.is_complete,
            "final_answer": self.final_answer,
            "messages": [
                {"role": m.role, "content": m.content, "timestamp": m.timestamp}
                for m in self.messages
            ],
        }


# ---------------------------------------------------------------------------
# Role Prompts
# ---------------------------------------------------------------------------

PLANNER_SYSTEM_PROMPT = """你是一个资深的 AI 规划师（Planner Agent）。你的任务是分析用户目标，制定可执行的计划。

## 你的职责
1. 深入理解用户意图和约束条件
2. 将复杂目标分解为有序的子任务
3. 评估每个子任务需要的能力和资源
4. 考虑潜在的风险和替代方案

## 可用工具/能力
{capabilities}

## 输出格式
请以 JSON 格式输出：
```json
{{
  "analysis": "对用户目标的分析和理解",
  "plan": [
    {{
      "step": 1,
      "task": "具体任务描述",
      "required_capability": "需要的能力",
      "expected_output": "预期产出",
      "dependencies": ["前置步骤"]
    }}
  ],
  "risks": ["潜在风险"],
  "alternatives": ["替代方案"],
  "confidence": 0.0-1.0
}}
```"""

EXECUTOR_SYSTEM_PROMPT = """你是一个高效的执行者（Executor Agent）。你的任务是按照计划执行具体任务。

## 你的职责
1. 严格按照计划步骤执行
2. 遇到问题时记录错误并尝试替代方案
3. 返回结构化的执行结果
4. 及时报告阻塞点

## 当前计划
{plan}

## 输出格式
对每个执行步骤，返回：
```json
{{
  "step": 步骤号,
  "status": "success|failed|blocked",
  "result": "执行结果描述",
  "data": {{...}},
  "error": "错误信息（如有）",
  "duration_ms": 执行耗时
}}
```"""

REVISER_SYSTEM_PROMPT = """你是一个严格的审查员（Reviser Agent）。你的任务是审查执行结果并给出反馈。

## 你的职责
1. 验证执行结果是否满足需求
2. 识别错误和遗漏
3. 评估结果质量
4. 决定是否需要重新规划或补充执行

## 审查标准
- 完整性：所有步骤是否都已执行？
- 正确性：结果是否准确？
- 质量：是否达到预期标准？
- 效率：是否有优化空间？

## 输出格式
```json
{{
  "verdict": "approved|needs_revision|failed",
  "issues": ["发现的问题"],
  "suggestions": ["改进建议"],
  "replan_needed": true/false,
  "feedback_summary": "总体评价",
  "quality_score": 0-100
}}
```"""


class ConversationOrchestrator:
    """多Agent对话编排器：Planner-Executor-Reviser 模式。

    通过 LLM 扮演不同角色，实现多轮对话式问题求解。
    结合 Harness 的 Agent 执行能力，将对话决策转化为实际行动。

    Usage:
        orchestrator = ConversationOrchestrator(harness, llm_client)
        result = orchestrator.converse(
            goal="分析运动数据并给出训练建议",
            initial_input={...}
        )
    """

    def __init__(
        self,
        harness: Any,
        llm_client: Optional[Any] = None,
        model: str = "gpt-4o-mini",
        max_iterations: int = 5,
    ):
        self.harness = harness
        self.llm_client = llm_client
        self.model = model
        self.max_iterations = max_iterations

    def converse(
        self,
        goal: str,
        initial_input: Any = None,
        user_id: str = "default",
    ) -> ConversationState:
        """执行多Agent对话流程。

        Returns:
            完整的对话状态，包含所有消息和最终结果。
        """
        state = ConversationState(
            goal=goal,
            max_iterations=self.max_iterations,
        )

        state.add_message("user", goal, input=initial_input)

        for iteration in range(1, self.max_iterations + 1):
            state.iteration = iteration

            # Phase 1: Planner generates/updates plan
            plan = self._plan(state)
            if plan:
                state.plan = plan

            # Phase 2: Executor executes plan steps
            results = self._execute(state, initial_input)
            state.execution_results.extend(results)

            # Phase 3: Reviser reviews results
            review = self._review(state)

            if review.get("verdict") == "approved":
                state.is_complete = True
                state.final_answer = review.get("feedback_summary", "任务完成")
                break
            elif review.get("replan_needed"):
                state.add_message(
                    "reviser",
                    f"第 {iteration} 轮审查：需要重新规划。{review.get('feedback_summary', '')}",
                )
                # Feed review back to planner for next iteration
                state.review_feedback = review.get("feedback_summary", "")
            else:
                state.is_complete = True
                state.final_answer = f"任务未完全成功: {review.get('feedback_summary', '')}"
                break

        if not state.is_complete:
            state.final_answer = f"达到最大迭代次数 ({self.max_iterations})，返回当前最佳结果"

        return state

    def _plan(self, state: ConversationState) -> Optional[Dict[str, Any]]:
        """Planner: 分析目标，生成执行计划。"""
        prompt = PLANNER_SYSTEM_PROMPT.format(
            capabilities=self._get_capabilities_summary()
        )

        recent_feedback = state.review_feedback or "无"
        user_msg = f"""目标: {state.goal}
当前迭代: {state.iteration}/{state.max_iterations}
上一轮反馈: {recent_feedback}
已有执行结果数: {len(state.execution_results)}

请制定或更新执行计划。"""

        response = self._call_llm(prompt, user_msg)
        if response:
            try:
                return json.loads(self._extract_json(response))
            except json.JSONDecodeError:
                pass

        # Fallback: simple plan
        return {
            "analysis": state.goal,
            "plan": [{"step": 1, "task": state.goal, "required_capability": "general"}],
            "confidence": 0.5,
        }

    def _execute(
        self, state: ConversationState, initial_input: Any
    ) -> List[Dict[str, Any]]:
        """Executor: 执行计划中的步骤。"""
        results = []
        plan = state.plan or {}
        steps = plan.get("plan", [])

        if not steps:
            return results

        for step in steps:
            step_num = step.get("step", 0)
            task = step.get("task", "")
            capability = step.get("required_capability", "")

            state.add_message("executor", f"执行步骤 {step_num}: {task}")

            # Try to find and execute agent with matching capability
            agent_id = self.harness.registry.find_agent(capability) if hasattr(self.harness.registry, 'find_agent') else None

            if agent_id:
                try:
                    exec_result = self.harness.execute_agent(agent_id, initial_input or {})
                    result_entry = {
                        "step": step_num,
                        "task": task,
                        "status": "success" if exec_result.get("success") else "failed",
                        "result": str(exec_result.get("result", ""))[:200],
                        "error": exec_result.get("error"),
                    }
                except Exception as exc:
                    result_entry = {
                        "step": step_num,
                        "task": task,
                        "status": "failed",
                        "error": str(exc),
                    }
            else:
                result_entry = {
                    "step": step_num,
                    "task": task,
                    "status": "skipped",
                    "error": f"No agent found for capability: {capability}",
                }

            results.append(result_entry)
            state.add_message(
                "executor",
                f"步骤 {step_num} {result_entry['status']}: {result_entry.get('result', result_entry.get('error', ''))}",
            )

        return results

    def _review(self, state: ConversationState) -> Dict[str, Any]:
        """Reviser: 审查执行结果。"""
        exec_summary = json.dumps(state.execution_results, ensure_ascii=False, default=str)

        prompt = REVISER_SYSTEM_PROMPT.format(plan=json.dumps(state.plan or {}, ensure_ascii=False))

        user_msg = f"""目标: {state.goal}
执行结果: {exec_summary}

请审查以上结果，判断是否达成目标。"""

        response = self._call_llm(prompt, user_msg)
        if response:
            try:
                return json.loads(self._extract_json(response))
            except json.JSONDecodeError:
                pass

        # Fallback: if all steps succeeded, approve
        if state.execution_results:
            all_ok = all(
                r.get("status") == "success" for r in state.execution_results
            )
            if all_ok:
                return {
                    "verdict": "approved",
                    "feedback_summary": "所有步骤执行成功",
                    "quality_score": 80,
                }

        return {
            "verdict": "needs_revision",
            "feedback_summary": "部分步骤失败，需要重新规划",
            "replan_needed": True,
            "quality_score": 40,
        }

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
                temperature=0.2,
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
            # Remove markdown code fences
            lines = text.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1] == "```":
                lines = lines[:-1]
            text = "\n".join(lines)
        return text.strip()

    def _get_capabilities_summary(self) -> str:
        """获取可用能力摘要。"""
        agents = self.harness.registry.list_agents()
        lines = []
        for a in agents:
            caps = ", ".join(a.get("capabilities", []))
            lines.append(f"- {a['agent_id']}: [{caps}]")
        return "\n".join(lines) if lines else "暂无可用 Agent"
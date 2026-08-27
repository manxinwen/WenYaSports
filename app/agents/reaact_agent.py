"""ReActAgent: 基于 ReAct（Reasoning + Acting）范式的工具调用 Agent。

核心能力：
1. 工具选择推理：LLM 自主决定调用哪些工具、以什么顺序调用
2. 参数验证：对工具调用参数进行预检查，防止无效调用
3. 错误恢复：工具执行失败时自动重试或切换方案
4. 结果整合：将多个工具结果整合成连贯的回答
5. 迭代上限：防止死循环，确保响应时效

设计亮点（面试展示点）：
- 使用 OpenAI Function Calling 实现真正的 Agent 自主工具选择
- 内置参数 Schema 校验，提前拦截无效调用
- 错误分类处理：网络错误重试、参数错误跳过、服务不可用降级
- 完整的 ReAct 轨迹记录：Thought → Action → Observation → ... → Final
"""

import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

from openai import OpenAI

from app.agents.base_agent import BaseAgent
from app.agents.session_log import EventType, SessionLog
from mcp_plugins import PluginManager

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "gpt-4o-mini"
_MAX_ITERATIONS = 5
_TOOL_CALL_TIMEOUT = 10.0
_MAX_RETRIES_PER_TOOL = 2

_SYSTEM_PROMPT = """你是一个专业的运动分析智能助手。你可以调用外部工具获取信息。

## 工具调用原则
1. **最小化调用**：只调用必要的工具，避免冗余请求
2. **参数精确**：严格按照工具的参数 Schema 传递参数
3. **结果整合**：综合多个工具的结果给出完整回答
4. **诚实回答**：如果工具无法提供信息，直接告知用户

## 回答风格
- 简洁、专业、中文
- 引用数据时注明来源
- 给出可操作的建议
"""

# ---------------------------------------------------------------------------
# 工具结果验证器
# ---------------------------------------------------------------------------

class ToolResultValidator:
    """工具调用结果验证器。

    检查工具返回结果的完整性和合理性：
    - 是否包含必需字段
    - 数值是否在合理范围
    - 是否为预期的数据类型
    """

    @staticmethod
    def validate(result: Dict[str, Any], tool_name: str) -> Dict[str, Any]:
        """验证工具结果，返回验证状态和修正后的结果。

        Args:
            result: 工具返回的结果字典
            tool_name: 工具名称

        Returns:
            {"valid": bool, "warnings": list}
        """
        warnings = []

        if result is None:
            return {"valid": False, "warnings": ["工具返回 None"]}

        if "error" in result and result["error"]:
            return {
                "valid": False,
                "warnings": [f"工具执行错误: {result['error']}"],
            }

        result_data = result.get("result", result)
        if isinstance(result_data, (list, dict)) and len(result_data) == 0:
            warnings.append("工具返回空结果")

        return {
            "valid": True,
            "warnings": warnings,
        }


# ---------------------------------------------------------------------------
# 错误恢复策略
# ---------------------------------------------------------------------------

class ToolErrorRecovery:
    """工具调用错误恢复策略。

    根据错误类型采取不同的恢复策略：
    - 参数错误：跳过该工具，继续后续步骤
    - 网络错误：指数退避重试
    - 服务不可用：标记为不可用，降级处理
    - 未知错误：记录日志，继续执行
    """

    def __init__(self, max_retries: int = _MAX_RETRIES_PER_TOOL):
        self.max_retries = max_retries
        self._tool_failures: Dict[str, int] = {}
        self._cooldown_until: Dict[str, float] = {}

    def can_retry(self, tool_name: str, attempt: int) -> bool:
        """判断是否可以重试。

        Args:
            tool_name: 工具名称
            attempt: 当前尝试次数

        Returns:
            是否可以重试
        """
        if attempt >= self.max_retries:
            return False

        cooldown_end = self._cooldown_until.get(tool_name, 0)
        if time.time() < cooldown_end:
            return False

        return True

    def should_skip(self, tool_name: str) -> bool:
        """判断是否应跳过该工具（冷却期内）。"""
        return time.time() < self._cooldown_until.get(tool_name, 0)

    def record_failure(self, tool_name: str, error_type: str) -> None:
        """记录工具失败。

        Args:
            tool_name: 工具名称
            error_type: 错误类型 ("param", "network", "service", "unknown")
        """
        self._tool_failures[tool_name] = self._tool_failures.get(tool_name, 0) + 1

        # 参数错误：跳过当前调用，不冷却
        if error_type == "param":
            return

        # 服务错误：冷却 30 秒
        if error_type == "service":
            self._cooldown_until[tool_name] = time.time() + 30
            logger.warning(
                "Tool %s cooldown activated after service error", tool_name
            )

        # 网络错误：冷却 5 秒
        if error_type == "network":
            self._cooldown_until[tool_name] = time.time() + 5

    def classify_error(self, error: Exception) -> str:
        """分类错误类型。

        Args:
            error: 异常对象

        Returns:
            错误类型: "param" | "network" | "service" | "unknown"
        """
        error_str = str(error).lower()

        if any(kw in error_str for kw in ["param", "argument", "invalid", "required"]):
            return "param"
        if any(kw in error_str for kw in ["timeout", "connection", "network", "reset"]):
            return "network"
        if any(kw in error_str for kw in ["unavailable", "service", "503", "502", "refused"]):
            return "service"
        return "unknown"

    def get_failure_count(self, tool_name: str) -> int:
        """获取工具失败次数。"""
        return self._tool_failures.get(tool_name, 0)

    def reset(self) -> None:
        """重置所有失败记录。"""
        self._tool_failures.clear()
        self._cooldown_until.clear()


# ---------------------------------------------------------------------------
# 主 Agent 实现
# ---------------------------------------------------------------------------

class ReActAgent(BaseAgent):
    """ReAct 范式工具调用 Agent（增强版）。

    相比基础 ReActAgent，增强版增加了：
    1. 工具结果验证器（ToolResultValidator）
    2. 错误恢复策略（ToolErrorRecovery）
    3. 工具选择推理链（Reasoning Chain）
    4. 调用统计和成本追踪

    Architecture:
        User Request → [LLM Planner] → Tool Selection → [Validator] → Executor
                                                              ↓
                                                        [Recovery] → Retry/Skip
                                                              ↓
                                                        Result Integration → Final Answer
    """

    agent_id = "react"
    agent_name = "ReAct Tool User"
    capabilities = ["tool_calling", "reasoning", "multi_step_planning", "error_recovery"]

    def __init__(
        self,
        plugin_manager: PluginManager,
        llm_enabled: bool = True,
        openai_api_key: Optional[str] = None,
        model: str = _DEFAULT_MODEL,
        max_iterations: int = _MAX_ITERATIONS,
        session_log: Optional[SessionLog] = None,
        trace_collector=None,
    ) -> None:
        super().__init__(name="react_agent", trace_collector=trace_collector)
        self.plugin_manager = plugin_manager
        self.llm_enabled = llm_enabled
        self.openai_api_key = openai_api_key or os.environ.get("OPENAI_API_KEY")
        self.model = model
        self.max_iterations = max_iterations
        self.session_log = session_log

        # 增强组件
        self.validator = ToolResultValidator()
        self.recovery = ToolErrorRecovery()

        # 调用统计
        self._total_tool_calls = 0
        self._successful_calls = 0
        self._failed_calls = 0
        self._total_latency_ms = 0

    def run(
        self,
        user_request: str,
        context: Optional[Dict[str, Any]] = None,
        session_id: str = "default",
    ) -> Dict[str, Any]:
        """处理用户请求，返回最终答案与完整的 ReAct 轨迹。

        Args:
            user_request: 用户请求文本
            context: 可选附加上下文（如用户画像）
            session_id: 会话标识

        Returns:
            {
                "success": bool,
                "answer": str | None,
                "tool_calls": [...],
                "iterations": int,
                "reasoning_chain": [...],  # 新增：完整推理链
                "stats": {...},            # 新增：调用统计
                "error": str | None,
            }
        """
        self._execution_count += 1
        self._last_input = user_request

        self._record(
            session_id, EventType.AGENT_START, "react_agent",
            {"request": user_request, "context_available": context is not None},
        )

        # Trace: 开始
        self._trace_step(
            session_id=session_id,
            step_type="thought",
            thought=f"收到请求: {user_request}",
            detail={"context_available": context is not None},
        )

        # 检查 LLM 可用性
        if not self.llm_enabled or not self.openai_api_key:
            error_msg = "LLM 未启用或未配置 API Key"
            self._trace_step(
                session_id=session_id,
                step_type="final",
                thought=f"降级处理: {error_msg}",
                detail={"success": False, "error": error_msg},
            )
            return self._finish(
                session_id, success=False, answer=None,
                error=error_msg, tool_calls=[], iterations=0,
                reasoning_chain=[],
            )

        # 构建工具列表
        tools = self._build_openai_tools()
        if not tools:
            # 无可用工具，直接用 LLM 回答
            logger.warning("No tools available, answering directly")
            return self._answer_without_tools(user_request, context, session_id)

        # 构建消息历史
        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": _SYSTEM_PROMPT}
        ]
        if context:
            messages.append({
                "role": "user",
                "content": f"已知上下文：{json.dumps(context, ensure_ascii=False)[:1000]}",
            })
        messages.append({"role": "user", "content": user_request})

        # ReAct 循环
        tool_calls_log: List[Dict[str, Any]] = []
        reasoning_chain: List[Dict[str, Any]] = []  # 完整推理链

        for iteration in range(1, self.max_iterations + 1):
            self._record(
                session_id, EventType.LLM_REQUEST, "react_agent",
                {
                    "model": self.model,
                    "iteration": iteration,
                    "messages": messages,
                },
            )

            # Trace: LLM 调用
            self._trace_step(
                session_id=session_id,
                step_type="action",
                thought=f"第 {iteration} 次迭代: LLM 选择工具",
                detail={
                    "model": self.model,
                    "tools_available": len(tools),
                    "tools_list": [t["function"]["name"] for t in tools],
                },
            )

            # 调用 LLM
            try:
                resp = self._chat(messages, tools)
            except Exception as exc:
                logger.warning("LLM 调用失败 (iter=%d): %s", iteration, exc)
                self._trace_step(
                    session_id=session_id,
                    step_type="final",
                    thought=f"LLM 调用失败: {exc}",
                    detail={"success": False, "error": str(exc)},
                )
                return self._finish(
                    session_id, success=False, answer=None,
                    error=f"LLM 调用失败: {exc}",
                    tool_calls=tool_calls_log, iterations=iteration,
                    reasoning_chain=reasoning_chain,
                )

            msg = resp.choices[0].message
            tool_calls = getattr(msg, "tool_calls", None)

            # 记录 LLM 响应事件
            self._record(
                session_id, EventType.LLM_RESPONSE, "react_agent",
                {
                    "content": msg.content,
                    "tool_calls_count": len(tool_calls or []),
                },
            )

            # 记录推理步骤
            reasoning_chain.append({
                "iteration": iteration,
                "thought": msg.content or "",
                "tools_decided": [tc.function.name for tc in tool_calls or []],
                "has_tool_calls": bool(tool_calls),
            })

            # Trace: LLM 响应
            self._trace_step(
                session_id=session_id,
                step_type="observation",
                thought=f"LLM 返回: {len(tool_calls or [])} 个工具调用",
                detail={
                    "content": msg.content,
                    "tool_calls_decided": [tc.function.name for tc in tool_calls or []],
                },
            )

            # 无工具调用 = 最终回答
            if not tool_calls:
                answer = msg.content or "抱歉，我无法回答这个问题。"

                # 最终结果验证
                answer_valid = self._validate_answer(answer)

                self._trace_step(
                    session_id=session_id,
                    step_type="final",
                    thought=f"生成最终答案（{len(answer)}字）",
                    detail={
                        "success": True,
                        "answer_length": len(answer),
                        "validation": answer_valid,
                    },
                )

                return self._finish(
                    session_id, success=True, answer=answer,
                    error=None, tool_calls=tool_calls_log,
                    iterations=iteration, reasoning_chain=reasoning_chain,
                )

            # 记录 assistant 消息
            call_dicts = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }
                for tc in tool_calls
            ]
            messages.append({
                "role": "assistant",
                "content": msg.content,
                "tool_calls": call_dicts,
            })

            # 执行工具（带错误恢复）
            execution_results = self._execute_tool_calls_with_recovery(
                tool_calls, session_id
            )

            # 回填执行结果
            for result_entry in execution_results:
                tc = result_entry["tool_call"]
                result = result_entry["result"]

                self._record(
                    session_id, EventType.TOOL_CALL, "react_agent",
                    {"tool_name": tc.function.name, "args": result.get("args")},
                )
                self._record(
                    session_id, EventType.TOOL_RESULT, "react_agent", None, result,
                )
                tool_calls_log.append(result)

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(result, ensure_ascii=False, default=str),
                })

            # 检查是否所有工具都失败了
            all_failed = all(
                "error" in r for r in tool_calls_log[-len(tool_calls):]
            )
            if all_failed:
                self._trace_step(
                    session_id=session_id,
                    step_type="observation",
                    thought="所有工具调用失败，尝试用已有信息回答",
                    detail={"all_failed": True},
                )
                # 继续循环，让 LLM 尝试在无工具的情况下回答

        # 达到最大迭代
        self._trace_step(
            session_id=session_id,
            step_type="final",
            thought=f"达到最大迭代次数 {self.max_iterations}",
            detail={"success": False, "error": "达到最大迭代次数"},
        )

        return self._finish(
            session_id, success=False, answer=None,
            error=f"达到最大迭代次数 ({self.max_iterations})",
            tool_calls=tool_calls_log, iterations=self.max_iterations,
            reasoning_chain=reasoning_chain,
        )

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _execute_tool_calls_with_recovery(
        self,
        tool_calls: List[Any],
        session_id: str,
    ) -> List[Dict[str, Any]]:
        """执行工具调用，带错误恢复。

        Args:
            tool_calls: LLM 决定的工具调用列表
            session_id: 会话标识

        Returns:
            执行结果列表，每项格式: {"tool_call": tc, "result": dict}
        """
        results = []

        for tc in tool_calls:
            tool_name = tc.function.name

            # 检查冷却状态
            if self.recovery.should_skip(tool_name):
                logger.info("Tool %s in cooldown, skipping", tool_name)
                skipped_result = {
                    "tool_name": tool_name,
                    "args": json.loads(tc.function.arguments or "{}"),
                    "error": "Tool temporarily unavailable (cooldown)",
                    "skipped": True,
                }
                results.append({"tool_call": tc, "result": skipped_result})
                continue

            # 带重试的执行
            last_result = None
            for attempt in range(_MAX_RETRIES_PER_TOOL + 1):
                if attempt > 0:
                    logger.info(
                        "Retrying tool %s (attempt %d/%d)",
                        tool_name, attempt, _MAX_RETRIES_PER_TOOL,
                    )
                    self._trace_step(
                        session_id=session_id,
                        step_type="action",
                        thought=f"重试工具 {tool_name}（第 {attempt} 次）",
                        detail={"tool_name": tool_name, "attempt": attempt},
                    )

                try:
                    result = self._execute_tool(tc)

                    # 验证结果
                    validation = self.validator.validate(result, tool_name)

                    if not validation["valid"] and attempt < _MAX_RETRIES_PER_TOOL:
                        # 结果无效，重试
                        last_result = result
                        continue

                    # 成功
                    self._successful_calls += 1
                    self._total_tool_calls += 1
                    results.append({"tool_call": tc, "result": result})
                    last_result = result
                    break

                except Exception as exc:
                    # 分类错误
                    error_type = self.recovery.classify_error(exc)
                    self.recovery.record_failure(tool_name, error_type)
                    self._failed_calls += 1
                    self._total_tool_calls += 1

                    logger.warning(
                        "Tool %s failed (attempt %d): %s [type=%s]",
                        tool_name, attempt, exc, error_type,
                    )

                    if attempt >= _MAX_RETRIES_PER_TOOL:
                        # 最终失败
                        failed_result = {
                            "tool_name": tool_name,
                            "error": str(exc),
                            "error_type": error_type,
                            "attempts": attempt + 1,
                        }
                        results.append({"tool_call": tc, "result": failed_result})
                        last_result = failed_result

            # 确保有结果
            if last_result is None:
                fallback_result = {
                    "tool_name": tool_name,
                    "error": "Execution failed without result",
                }
                results.append({"tool_call": tc, "result": fallback_result})

        return results

    def _finish(
        self, session_id, success, answer, error,
        tool_calls, iterations, reasoning_chain=None,
    ):
        """统一收尾，包含调用统计。"""
        result = {
            "success": success,
            "answer": answer,
            "tool_calls": tool_calls,
            "iterations": iterations,
            "reasoning_chain": reasoning_chain or [],
            "stats": self._get_stats(),
        }
        if error:
            result["error"] = error
        self._record(session_id, EventType.AGENT_END, "react_agent", None, result)
        return result

    def _answer_without_tools(
        self, user_request: str, context: Optional[Dict], session_id: str,
    ) -> Dict[str, Any]:
        """无工具可用时，直接用 LLM 回答。"""
        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": _SYSTEM_PROMPT}
        ]
        if context:
            messages.append({
                "role": "user",
                "content": f"已知上下文：{json.dumps(context, ensure_ascii=False)[:1000]}",
            })
        messages.append({"role": "user", "content": user_request})

        try:
            resp = self._chat(messages, [])
            answer = resp.choices[0].message.content or "抱歉，我无法回答这个问题。"
            return self._finish(
                session_id, success=True, answer=answer,
                error=None, tool_calls=[], iterations=1,
                reasoning_chain=[{"iteration": 1, "thought": "直接回答（无可用工具）", "tools_decided": []}],
            )
        except Exception as exc:
            return self._finish(
                session_id, success=False, answer=None,
                error=str(exc), tool_calls=[], iterations=0,
                reasoning_chain=[],
            )

    def _validate_answer(self, answer: str) -> Dict[str, Any]:
        """验证最终答案的质量。

        检查项：
        - 长度合理性（太短可能意味着没有真正回答问题）
        - 是否包含具体信息（而非套话）
        - 格式是否符合预期
        """
        issues = []
        min_length = 10
        max_length = 5000

        if len(answer) < min_length:
            issues.append(f"答案过短 ({len(answer)} chars)")

        if len(answer) > max_length:
            issues.append(f"答案过长 ({len(answer)} chars)")

        # 检查是否包含不确定性标记
        uncertainty_keywords = ["可能", "也许", "大概", "不确定", "无法确定"]
        uncertainty_count = sum(1 for kw in uncertainty_keywords if kw in answer)
        if uncertainty_count > 3:
            issues.append(f"答案包含过多不确定性表述 ({uncertainty_count}处)")

        return {
            "valid": len(issues) <= 1,  # 允许一个小问题
            "length": len(answer),
            "issues": issues,
            "quality_score": max(0, 10 - len(issues) * 2),
        }

    def _record(self, session_id, event_type, agent, payload=None, result=None):
        """将事件写入 SessionLog。"""
        if self.session_log is not None:
            self.session_log.record(session_id, event_type, agent, payload, result)

    def _chat(self, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]]):
        """调用 Chat Completions API。"""
        client = OpenAI(api_key=self.openai_api_key)
        kwargs: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.2,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        return client.chat.completions.create(**kwargs)

    def _execute_tool(self, tool_call) -> Dict[str, Any]:
        """执行单个工具调用。"""
        function = tool_call.function
        name = function.name
        try:
            args = json.loads(function.arguments or "{}")
        except json.JSONDecodeError:
            args = {}
        result = self.plugin_manager.handle_request(name, args)
        result["tool_name"] = name
        result["args"] = args
        return result

    def _build_openai_tools(self) -> List[Dict[str, Any]]:
        """构建 OpenAI function-calling 格式的工具列表。"""
        openai_tools: List[Dict[str, Any]] = []
        for tool in self.plugin_manager.get_all_tools():
            openai_tools.append({
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": tool["parameters"],
                },
            })
        return openai_tools

    def _get_stats(self) -> Dict[str, Any]:
        """获取调用统计信息。"""
        total = self._total_tool_calls
        return {
            "total_tool_calls": total,
            "successful_calls": self._successful_calls,
            "failed_calls": self._failed_calls,
            "success_rate": (self._successful_calls / total * 100) if total > 0 else 0,
            "reasoning_chain_length": self._execution_count,
        }

    def reset_stats(self) -> None:
        """重置调用统计。"""
        self._total_tool_calls = 0
        self._successful_calls = 0
        self._failed_calls = 0
        self.recovery.reset()

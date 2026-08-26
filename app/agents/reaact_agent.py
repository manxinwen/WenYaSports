"""ReActAgent: 基于 ReAct（Reasoning + Acting）范式的工具调用 Agent。

核心价值：
- 将 PluginManager 暴露的 MCP 工具定义转换为 OpenAI function-calling 格式；
- LLM 在「思考 → 决定调用工具 → 执行 → 结果回填 → 再思考」循环中自主完成
  多工具编排，而不再像 RecommendationAgent 那样仅做单轮文本生成；
- 具备迭代上限与错误隔离，防止死循环与单点故障拖垮上层。
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional

from openai import OpenAI

from app.agents.base_agent import BaseAgent
from app.agents.session_log import EventType, SessionLog
from mcp_plugins import PluginManager

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "gpt-4o-mini"
_MAX_ITERATIONS = 5

_SYSTEM_PROMPT = (
    "你是一个运动分析助手。你可以调用外部工具获取实时信息（如天气、路线等），"
    "也可以基于已有数据直接回答。需要工具时请调用合适的工具，"
    "并根据工具返回结果给出简洁、专业的中文回答。"
)


class ReActAgent(BaseAgent):
    """在 LLM 与 PluginManager 之间驱动工具调用循环的 Agent。

    :param plugin_manager: 已加载工具的 PluginManager 实例。
    :param llm_enabled: 是否启用 LLM（便于测试与降级）。
    :param openai_api_key: OpenAI API Key；缺省时读取环境变量 OPENAI_API_KEY。
    :param model: 使用的模型名。
    :param max_iterations: 工具调用循环的最大轮数。
    """

    def __init__(
        self,
        plugin_manager: PluginManager,
        llm_enabled: bool = True,
        openai_api_key: Optional[str] = None,
        model: str = _DEFAULT_MODEL,
        max_iterations: int = _MAX_ITERATIONS,
        session_log: Optional[SessionLog] = None,
    ) -> None:
        self.plugin_manager = plugin_manager
        self.llm_enabled = llm_enabled
        self.openai_api_key = openai_api_key or os.environ.get("OPENAI_API_KEY")
        self.model = model
        self.max_iterations = max_iterations
        self.session_log = session_log

    # ------------------------------------------------------------------
    # 主入口：ReAct 循环
    # ------------------------------------------------------------------
    def run(
        self,
        user_request: str,
        context: Optional[Dict[str, Any]] = None,
        session_id: str = "default",
    ) -> Dict[str, Any]:
        """处理用户请求，返回最终答案与工具调用轨迹。

        :param user_request: 用户请求文本。
        :param context: 可选附加上下文（如用户画像）。
        :param session_id: 会话标识，用于事件溯源日志。
        :return: ``{"success", "answer", "tool_calls", "iterations", "error"}``。
        """
        self._record(
            session_id, EventType.AGENT_START, "react_agent",
            {"request": user_request, "context": context},
        )
        if not self.llm_enabled or not self.openai_api_key:
            return self._finish(
                session_id,
                success=False,
                answer=None,
                error="LLM 未启用或未配置 API Key",
                tool_calls=[],
                iterations=0,
            )

        tools = self._build_openai_tools()
        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": _SYSTEM_PROMPT}
        ]
        if context:
            messages.append(
                {
                    "role": "user",
                    "content": f"已知上下文：{json.dumps(context, ensure_ascii=False)}",
                }
            )
        messages.append({"role": "user", "content": user_request})

        tool_calls_log: List[Dict[str, Any]] = []
        for iteration in range(1, self.max_iterations + 1):
            self._record(
                session_id, EventType.LLM_REQUEST, "react_agent",
                {"model": self.model, "messages": messages},
            )
            try:
                resp = self._chat(messages, tools)
            except Exception as exc:  # noqa: BLE001 - LLM 故障需兜底
                logger.warning("LLM 调用失败：%s", exc)
                return self._finish(
                    session_id,
                    success=False,
                    answer=None,
                    error=f"LLM 调用失败：{exc}",
                    tool_calls=tool_calls_log,
                    iterations=iteration,
                )

            msg = resp.choices[0].message
            tool_calls = getattr(msg, "tool_calls", None)
            self._record(
                session_id, EventType.LLM_RESPONSE, "react_agent",
                None,
                {
                    "content": msg.content,
                    "tool_calls": [tc.function.name for tc in tool_calls or []],
                },
            )
            if not tool_calls:
                return self._finish(
                    session_id,
                    success=True,
                    answer=msg.content,
                    error=None,
                    tool_calls=tool_calls_log,
                    iterations=iteration,
                )

            # 记录 assistant 的调用决策，并回填到对话历史
            call_dicts = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }
                for tc in tool_calls
            ]
            messages.append(
                {"role": "assistant", "content": msg.content, "tool_calls": call_dicts}
            )

            # 逐个执行工具，结果作为 tool 消息回填
            for tc in tool_calls:
                result = self._execute_tool(tc)
                self._record(
                    session_id, EventType.TOOL_CALL, "react_agent",
                    {"tool_name": tc.function.name, "args": result.get("args")},
                )
                self._record(
                    session_id, EventType.TOOL_RESULT, "react_agent", None, result
                )
                tool_calls_log.append(result)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": json.dumps(result, ensure_ascii=False),
                    }
                )

        return self._finish(
            session_id,
            success=False,
            answer=None,
            error=f"达到最大迭代次数 {self.max_iterations}",
            tool_calls=tool_calls_log,
            iterations=self.max_iterations,
        )

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------
    def _finish(self, session_id, success, answer, error, tool_calls, iterations):
        """统一收尾：记录 AGENT_END 事件并组装返回值。"""
        result = {
            "success": success,
            "answer": answer,
            "tool_calls": tool_calls,
            "iterations": iterations,
        }
        if error:
            result["error"] = error
        self._record(session_id, EventType.AGENT_END, "react_agent", None, result)
        return result

    def _record(self, session_id, event_type, agent, payload=None, result=None):
        """将事件写入 SessionLog（未接入时静默跳过）。"""
        if self.session_log is not None:
            self.session_log.record(session_id, event_type, agent, payload, result)

    def _chat(self, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]]):
        """调用 OpenAI Chat Completions，注入工具定义。"""
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
        """通过 PluginManager 执行单个工具调用，返回结果字典。"""
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
        """将 PluginManager 的 MCP 工具定义转换为 OpenAI function-calling 格式。"""
        openai_tools: List[Dict[str, Any]] = []
        for tool in self.plugin_manager.get_all_tools():
            openai_tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": tool["name"],
                        "description": tool["description"],
                        "parameters": tool["parameters"],
                    },
                }
            )
        return openai_tools

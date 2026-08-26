"""工具执行三阶段管线：pre-execute → execute → post-execute。

设计借鉴 DeepSeek Harness 的 tools/pre-execute → execute → post-execute 管线：

- **pre-execute 钩子** 可在执行前拦截/短路：缓存命中直接返回、限流拒绝、
  权限校验等；
- **execute** 为插件真实执行；
- **post-execute 钩子** 观察结果：写缓存、审计落盘、采集指标等。

预置钩子（均为工厂函数，返回 ``(pre, post)``）：
- :func:`cache_hook`：结果缓存（TTL），命中短路、成功结果回写；
- :func:`rate_limit_hook`：滑动窗口限流，超限拒绝；
- :func:`audit_hook`：将工具调用与结果写入审计日志（可接入 SessionLog）。
"""

import json
import logging
import threading
import time
from collections import defaultdict, deque
from typing import Any, Callable, Deque, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

#: pre-execute 钩子的决策动作
ACTION_PROCEED = "proceed"
ACTION_USE_CACHE = "use_cache"
ACTION_BLOCK = "block"

PreHook = Callable[[str, str, Dict[str, Any]], Optional[Dict[str, Any]]]
PostHook = Callable[[str, str, Dict[str, Any], Dict[str, Any]], None]


class ToolPipeline:
    """组装 pre/post 钩子的执行管线。

    用法：:

        pipeline = ToolPipeline()
        pre, post = cache_hook(TTLCache(...))
        pipeline.add_pre_hook(pre)
        pipeline.add_post_hook(post)
        result = pipeline.execute(lambda p, t, params: plugin.execute(t, params), "weather", "get_current_weather", {})
    """

    def __init__(self) -> None:
        self._pre_hooks: list[PreHook] = []
        self._post_hooks: list[PostHook] = []

    def add_pre_hook(self, hook: PreHook) -> None:
        """注册 pre-execute 钩子（按注册顺序执行）。"""
        self._pre_hooks.append(hook)

    def add_post_hook(self, hook: PostHook) -> None:
        """注册 post-execute 钩子（按注册顺序执行）。"""
        self._post_hooks.append(hook)

    def execute(
        self,
        executor: Callable[[str, str, Dict[str, Any]], Dict[str, Any]],
        plugin_name: str,
        tool_name: str,
        parameters: Dict[str, Any],
    ) -> Dict[str, Any]:
        """执行工具，经过 pre → execute → post 三阶段。

        pre 钩子返回 ``{"action": "use_cache", "value": ...}`` 时短路返回缓存值；
        返回 ``{"action": "block", "reason": ...}`` 时短路返回错误；
        其余视为放行。post 钩子只观察、不改写结果。
        """
        for hook in self._pre_hooks:
            try:
                decision = hook(plugin_name, tool_name, parameters)
            except Exception:  # noqa: BLE001 - 钩子异常不阻断执行
                logger.exception(
                    "pre-execute 钩子异常，已放行：%s.%s", plugin_name, tool_name
                )
                continue
            if not decision or decision.get("action") == ACTION_PROCEED:
                continue
            if decision.get("action") == ACTION_USE_CACHE:
                logger.info("缓存命中：%s.%s", plugin_name, tool_name)
                return decision["value"]
            if decision.get("action") == ACTION_BLOCK:
                return {
                    "success": False,
                    "error": decision.get("reason", "被 pre-execute 钩子拦截"),
                }

        result = executor(plugin_name, tool_name, parameters)
        for hook in self._post_hooks:
            try:
                hook(plugin_name, tool_name, parameters, result)
            except Exception:  # noqa: BLE001 - 钩子异常不影响结果返回
                logger.exception(
                    "post-execute 钩子异常：%s.%s", plugin_name, tool_name
                )
        return result


# ----------------------------------------------------------------------
# 预置钩子
# ----------------------------------------------------------------------
def _cache_key(plugin_name: str, tool_name: str, parameters: Dict[str, Any]) -> str:
    """生成稳定的缓存键（参数排序后 JSON 序列化）。"""
    return json.dumps(
        [plugin_name, tool_name, parameters], sort_keys=True, ensure_ascii=False
    )


def cache_hook(cache) -> Tuple[PreHook, PostHook]:
    """结果缓存钩子：命中短路返回缓存值，成功的执行结果回写缓存。

    :param cache: 任意 ``__contains__`` / ``__getitem__`` / ``__setitem__``
                  的对象（推荐 cachetools.TTLCache）。
    """

    def pre(plugin_name: str, tool_name: str, parameters: Dict[str, Any]):
        key = _cache_key(plugin_name, tool_name, parameters)
        if key in cache:
            return {"action": ACTION_USE_CACHE, "value": cache[key], "cache_key": key}
        return {"action": ACTION_PROCEED, "cache_key": key}

    def post(plugin_name: str, tool_name: str, parameters: Dict[str, Any], result: Dict[str, Any]):
        if result.get("success"):
            cache[_cache_key(plugin_name, tool_name, parameters)] = result

    return pre, post


def rate_limit_hook(
    max_calls: int = 10, window_seconds: float = 60.0
) -> Tuple[PreHook, Optional[PostHook]]:
    """滑动窗口限流钩子：按 (插件, 工具) 维度限制窗口内调用次数。

    :param max_calls: 窗口内允许的最大调用次数。
    :param window_seconds: 滑动窗口时长（秒）。
    """
    buckets: Dict[Tuple[str, str], Deque[float]] = defaultdict(deque)
    lock = threading.Lock()

    def pre(plugin_name: str, tool_name: str, parameters: Dict[str, Any]):
        now = time.monotonic()
        key = (plugin_name, tool_name)
        with lock:
            queue = buckets[key]
            while queue and now - queue[0] > window_seconds:
                queue.popleft()
            if len(queue) >= max_calls:
                return {
                    "action": ACTION_BLOCK,
                    "reason": f"限流：{max_calls} 次/{window_seconds:g}s 内已达到上限",
                }
            queue.append(now)
            return {"action": ACTION_PROCEED}

    return pre, None


def audit_hook(log, session_id: str = "default") -> Tuple[PreHook, PostHook]:
    """审计钩子：将工具调用与结果写入日志。

    :param log: 任意具备 ``record(session_id, event_type, agent, payload, result)``
                的对象（如 app.agents.session_log.SessionLog）。
    """
    from app.agents.session_log import EventType

    def pre(plugin_name: str, tool_name: str, parameters: Dict[str, Any]):
        log.record(
            session_id,
            EventType.TOOL_CALL,
            plugin_name,
            {"tool_name": tool_name, "args": parameters},
        )
        return {"action": ACTION_PROCEED}

    def post(plugin_name: str, tool_name: str, parameters: Dict[str, Any], result: Dict[str, Any]):
        log.record(session_id, EventType.TOOL_RESULT, plugin_name, None, result)

    return pre, post

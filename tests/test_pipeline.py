"""工具执行管线（ToolPipeline）与 PluginManager 集成测试。

覆盖：三阶段顺序、缓存命中短路、限流拦截、审计落盘、
自定义拦截钩子、异常隔离、向后兼容（无钩子时行为不变）。
"""

import json
from unittest import mock

from app.agents.session_log import EventType, SessionLog
from cachetools import TTLCache

from mcp_plugins import PluginManager
from mcp_plugins.pipeline import ToolPipeline, audit_hook, cache_hook, rate_limit_hook

_WEATHER_CONFIG = {
    "plugins": [
        {
            "name": "weather",
            "enabled": True,
            "config": {"api_key": "test-key"},
        }
    ]
}


def _weather_response():
    return {
        "name": "Beijing",
        "main": {"temp": 25.0, "humidity": 55},
        "wind": {"speed": 3.0},
        "weather": [{"description": "晴"}],
    }


def _manager() -> PluginManager:
    return PluginManager(config=_WEATHER_CONFIG)


# ----------------------------------------------------------------------
# 基础管线行为
# ----------------------------------------------------------------------
def test_pipeline_executes_in_order():
    order = []
    pipeline = ToolPipeline()

    def pre_hook(p, t, params):
        order.append("pre")
        return None

    def post_hook(p, t, params, result):
        order.append("post")

    pipeline.add_pre_hook(pre_hook)
    pipeline.add_post_hook(post_hook)

    def executor(p, t, params):
        order.append("execute")
        return {"success": True}

    result = pipeline.execute(executor, "w", "t", {})
    assert result == {"success": True}
    assert order == ["pre", "execute", "post"]


def test_pre_hook_block_short_circuits():
    pipeline = ToolPipeline()

    def block(p, t, params):
        return {"action": "block", "reason": "no permission"}

    executed = []

    def executor(p, t, params):
        executed.append(True)
        return {"success": True}

    pipeline.add_pre_hook(block)
    result = pipeline.execute(executor, "w", "t", {})
    assert result == {"success": False, "error": "no permission"}
    assert executed == []


def test_pre_hook_error_does_not_block_execution():
    pipeline = ToolPipeline()
    executed = []

    def bad_hook(p, t, params):
        raise RuntimeError("boom")

    def executor(p, t, params):
        executed.append(True)
        return {"success": True}

    pipeline.add_pre_hook(bad_hook)
    result = pipeline.execute(executor, "w", "t", {})
    assert result["success"] is True
    assert executed == [True]


# ----------------------------------------------------------------------
# 缓存钩子
# ----------------------------------------------------------------------
@mock.patch("mcp_plugins.plugins.weather.weather_plugin.requests.Session.get")
def test_cache_hook_returns_cached_result(mock_get):
    mock_get.return_value.status_code = 200
    mock_get.return_value.json.return_value = _weather_response()

    cache = TTLCache(maxsize=16, ttl=60)
    pre, post = cache_hook(cache)
    pipeline = ToolPipeline()
    pipeline.add_pre_hook(pre)
    pipeline.add_post_hook(post)

    manager = _manager()
    # 第一次：真正执行（走插件 -> 外部 API）
    r1 = pipeline.execute(
        lambda p, t, params: manager.execute_tool(p, t, params),
        "weather",
        "get_current_weather",
        {"city": "Beijing"},
    )
    # 第二次：应命中缓存，不再次调用外部 API
    r2 = pipeline.execute(
        lambda p, t, params: manager.execute_tool(p, t, params),
        "weather",
        "get_current_weather",
        {"city": "Beijing"},
    )
    assert r1["success"] is True
    assert r2["success"] is True
    assert mock_get.call_count == 1


def test_cache_only_stores_success_results():
    cache = TTLCache(maxsize=16, ttl=60)
    pre, post = cache_hook(cache)
    pipeline = ToolPipeline()
    pipeline.add_pre_hook(pre)
    pipeline.add_post_hook(post)

    calls = {"n": 0}

    def executor(p, t, params):
        calls["n"] += 1
        return {"success": False, "error": "api down"}

    pipeline.execute(executor, "w", "t", {})
    pipeline.execute(executor, "w", "t", {})
    # 失败结果不缓存，两次都真正执行
    assert calls["n"] == 2


# ----------------------------------------------------------------------
# 限流钩子
# ----------------------------------------------------------------------
def test_rate_limit_blocks_after_max_calls():
    pre, _ = rate_limit_hook(max_calls=2, window_seconds=60)
    pipeline = ToolPipeline()
    pipeline.add_pre_hook(pre)

    executed = {"n": 0}

    def executor(p, t, params):
        executed["n"] += 1
        return {"success": True}

    assert pipeline.execute(executor, "w", "t", {})["success"] is True
    assert pipeline.execute(executor, "w", "t", {})["success"] is True
    third = pipeline.execute(executor, "w", "t", {})
    assert third["success"] is False
    assert "限流" in third["error"]
    assert executed["n"] == 2


# ----------------------------------------------------------------------
# 审计钩子
# ----------------------------------------------------------------------
def test_audit_hook_records_tool_call_and_result():
    log = SessionLog()
    pre, post = audit_hook(log, session_id="s1")
    pipeline = ToolPipeline()
    pipeline.add_pre_hook(pre)
    pipeline.add_post_hook(post)

    pipeline.execute(
        lambda p, t, params: {"success": True, "city": params["city"]},
        "weather",
        "get_current_weather",
        {"city": "Beijing"},
    )

    events = log.events("s1")
    assert [e.event_type for e in events] == [
        EventType.TOOL_CALL,
        EventType.TOOL_RESULT,
    ]
    assert events[0].agent == "weather"
    assert events[0].payload["tool_name"] == "get_current_weather"
    assert events[1].result["city"] == "Beijing"


# ----------------------------------------------------------------------
# PluginManager 集成 + 向后兼容
# ----------------------------------------------------------------------
@mock.patch("mcp_plugins.plugins.weather.weather_plugin.requests.Session.get")
def test_manager_without_hooks_unchanged(mock_get):
    """未启用任何钩子时，execute_tool 行为与之前完全一致。"""
    mock_get.return_value.status_code = 200
    mock_get.return_value.json.return_value = _weather_response()
    manager = _manager()
    result = manager.execute_tool("weather", "get_current_weather", {"city": "Beijing"})
    assert result["success"] is True
    assert result["city"] == "Beijing"


@mock.patch("mcp_plugins.plugins.weather.weather_plugin.requests.Session.get")
def test_manager_enable_cache_via_handle_request(mock_get):
    mock_get.return_value.status_code = 200
    mock_get.return_value.json.return_value = _weather_response()

    manager = _manager()
    manager.enable_cache(ttl=60)

    r1 = manager.handle_request("get_current_weather", {"city": "Beijing"})
    r2 = manager.handle_request("get_current_weather", {"city": "Beijing"})
    assert r1["success"] is True and r2["success"] is True
    # 第二次命中缓存，外部 API 只被调用一次
    assert mock_get.call_count == 1


@mock.patch("mcp_plugins.plugins.weather.weather_plugin.requests.Session.get")
def test_manager_enable_rate_limit(mock_get):
    mock_get.return_value.status_code = 200
    mock_get.return_value.json.return_value = _weather_response()

    manager = _manager()
    manager.enable_rate_limit(max_calls=1, window_seconds=60)

    first = manager.handle_request("get_current_weather", {"city": "Beijing"})
    second = manager.handle_request("get_current_weather", {"city": "Beijing"})
    assert first["success"] is True
    assert second["success"] is False
    assert "限流" in second["error"]


def test_manager_enable_audit_writes_session_log():
    log = SessionLog()
    manager = _manager()
    manager.enable_audit(log, session_id="s1")

    manager.handle_request("get_current_weather", {"city": "Beijing"})

    events = log.events("s1")
    assert len(events) == 2
    assert events[0].event_type == EventType.TOOL_CALL
    assert events[1].event_type == EventType.TOOL_RESULT
    # 审计内容可直接导出为人类可读文本
    assert "get_current_weather" in log.export_text("s1")


def test_cache_key_is_stable_and_sorted():
    from mcp_plugins.pipeline import _cache_key

    k1 = _cache_key("w", "t", {"city": "Beijing", "a": 1})
    k2 = _cache_key("w", "t", {"a": 1, "city": "Beijing"})
    assert k1 == k2
    data = json.loads(k1)
    assert data[2] == {"a": 1, "city": "Beijing"}

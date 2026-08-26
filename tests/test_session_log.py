"""事件溯源会话日志（SessionLog）单元测试。

覆盖：append-only 事件流、按会话过滤与回放、JSONL 持久化与重建
（断点续跑）、MessageBus 接入、ReActAgent 轨迹记录。
"""

import json
from types import SimpleNamespace
from unittest import mock

from app.agents.protocol import AgentMessage, MessageBus, MessageType
from app.agents.reaact_agent import ReActAgent
from app.agents.session_log import (
    EventType,
    SessionLog,
    attach_message_bus_logging,
)
from mcp_plugins import PluginManager

_WEATHER_CONFIG = {
    "plugins": [
        {
            "name": "weather",
            "enabled": True,
            "config": {"api_key": "test-key"},
        }
    ]
}


def _manager() -> PluginManager:
    return PluginManager(config=_WEATHER_CONFIG)


# ----------------------------------------------------------------------
# SessionLog 基础行为
# ----------------------------------------------------------------------
def test_record_appends_events_with_increasing_sequence():
    log = SessionLog()
    e1 = log.record("s1", EventType.TOOL_CALL, "react", {"tool_name": "weather"})
    e2 = log.record("s1", EventType.TOOL_RESULT, "react", None, {"ok": True})
    assert e1.sequence == 1
    assert e2.sequence == 2
    assert e2.event_type == EventType.TOOL_RESULT
    assert e2.result == {"ok": True}


def test_events_filter_by_session_id():
    log = SessionLog()
    log.record("s1", EventType.AGENT_START, "react", {})
    log.record("s2", EventType.AGENT_START, "react", {})
    log.record("s1", EventType.AGENT_END, "react", {})
    assert len(log.events("s1")) == 2
    assert len(log.events("s2")) == 1
    assert len(log.events()) == 3


def test_replay_returns_ordered_events():
    log = SessionLog()
    log.record("s1", EventType.LLM_REQUEST, "react", {"round": 1})
    log.record("s1", EventType.TOOL_CALL, "react", {"round": 2})
    events = log.replay("s1")
    assert [e.event_type for e in events] == [
        EventType.LLM_REQUEST,
        EventType.TOOL_CALL,
    ]


def test_export_text_is_human_readable():
    log = SessionLog()
    log.record("s1", EventType.TOOL_CALL, "react", {"tool_name": "weather"})
    text = log.export_text("s1")
    assert "s1" in text
    assert "tool_call" in text
    assert "weather" in text


# ----------------------------------------------------------------------
# JSONL 持久化与重建（断点续跑）
# ----------------------------------------------------------------------
def test_jsonl_persistence_and_load(tmp_path):
    path = str(tmp_path / "session.jsonl")
    log = SessionLog(path)
    log.record("s1", EventType.AGENT_START, "react", {"request": "北京天气"})
    log.record("s1", EventType.TOOL_CALL, "react", {"tool_name": "weather"})
    log.close()

    # 从文件重建，事件完整且可继续追加
    reloaded = SessionLog.load(path)
    assert len(reloaded.replay("s1")) == 2
    assert reloaded.replay("s1")[0].payload == {"request": "北京天气"}

    # 重建后可继续追加，sequence 不冲突
    reloaded.record("s1", EventType.TOOL_RESULT, "react", None, {"ok": True})
    assert reloaded.replay("s1")[-1].sequence == 3


# ----------------------------------------------------------------------
# MessageBus 接入
# ----------------------------------------------------------------------
def test_message_bus_logging_records_agent_communication():
    log = SessionLog()
    bus = MessageBus()
    attach_message_bus_logging(bus, log, session_id="s1")

    bus.publish(
        AgentMessage("coordinator", "memory", MessageType.REQUEST, {"user_id": "u1"})
    )
    bus.publish(
        AgentMessage("memory", "coordinator", MessageType.RESPONSE, {"ok": True})
    )

    events = log.events("s1")
    assert len(events) == 2
    assert events[0].event_type == "message.request"
    assert events[0].agent == "coordinator"
    assert events[0].payload["payload"] == {"user_id": "u1"}


# ----------------------------------------------------------------------
# ReActAgent 轨迹记录
# ----------------------------------------------------------------------
@mock.patch("app.agents.reaact_agent.OpenAI")
@mock.patch("mcp_plugins.plugins.weather.weather_plugin.requests.Session.get")
def test_react_agent_records_full_trajectory(mock_get, mock_openai):
    mock_get.return_value.status_code = 200
    mock_get.return_value.json.return_value = {
        "name": "Beijing",
        "main": {"temp": 25.0, "humidity": 55},
        "wind": {"speed": 3.0},
        "weather": [{"description": "晴"}],
    }

    def _tool_call():
        return SimpleNamespace(
            id="call_1",
            function=SimpleNamespace(
                name="get_current_weather", arguments='{"city": "Beijing"}'
            ),
        )

    def _resp(message):
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])

    tool_message = SimpleNamespace(content=None, tool_calls=[_tool_call()])
    final_message = SimpleNamespace(content="北京 25°C，晴", tool_calls=None)
    fake_client = mock_openai.return_value
    fake_client.chat.completions.create.side_effect = [
        _resp(tool_message),
        _resp(final_message),
    ]

    log = SessionLog()
    agent = ReActAgent(
        _manager(), llm_enabled=True, openai_api_key="key", session_log=log
    )
    agent.run("北京天气？", session_id="s1")

    events = log.replay("s1")
    types = [e.event_type for e in events]
    # 关键不变量：模型/Agent 看到的一切都应可从日志重建
    assert types[0] == EventType.AGENT_START
    assert EventType.LLM_REQUEST in types
    assert EventType.LLM_RESPONSE in types
    assert EventType.TOOL_CALL in types
    assert EventType.TOOL_RESULT in types
    assert types[-1] == EventType.AGENT_END

    # 验证工具轨迹内容完整
    tool_call = next(e for e in events if e.event_type == EventType.TOOL_CALL)
    assert tool_call.payload == {
        "tool_name": "get_current_weather",
        "args": {"city": "Beijing"},
    }
    tool_result = next(e for e in events if e.event_type == EventType.TOOL_RESULT)
    assert tool_result.result["success"] is True

    # LLM 请求中记录了完整消息（可重建模型所见）
    llm_req = next(e for e in events if e.event_type == EventType.LLM_REQUEST)
    assert "北京天气？" in [m.get("content") for m in llm_req.payload["messages"]]


def test_react_agent_without_log_is_unchanged():
    """未接入 SessionLog 时，ReActAgent 行为与日志无关、不报错。"""
    agent = ReActAgent(_manager(), llm_enabled=False)
    result = agent.run("北京天气")
    assert result["success"] is False

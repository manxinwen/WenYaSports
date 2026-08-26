"""ReActAgent（工具调用循环）单元测试。

通过 mock OpenAI 客户端模拟「先调用工具 → 再生成答案」的两轮交互，
验证：工具定义转换、工具执行、结果回填、迭代上限与降级。
"""

from types import SimpleNamespace
from unittest import mock

from app.agents.reaact_agent import ReActAgent
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


def _make_tool_call(name, arguments):
    return SimpleNamespace(
        id="call_1",
        function=SimpleNamespace(name=name, arguments=arguments),
    )


def _make_response(message):
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def _make_final_message(text):
    return SimpleNamespace(content=text, tool_calls=None)


# ----------------------------------------------------------------------
# 工具定义转换
# ----------------------------------------------------------------------
def test_build_openai_tools_uses_mcp_definitions():
    agent = ReActAgent(_manager(), llm_enabled=True, openai_api_key="key")
    tools = agent._build_openai_tools()
    assert len(tools) == 1
    fn = tools[0]["function"]
    assert fn["name"] == "get_current_weather"
    assert fn["parameters"]["type"] == "object"
    assert "city" in fn["parameters"]["properties"]


# ----------------------------------------------------------------------
# ReAct 循环：工具调用 → 结果回填 → 最终答案
# ----------------------------------------------------------------------
@mock.patch("app.agents.reaact_agent.OpenAI")
@mock.patch("mcp_plugins.plugins.weather.weather_plugin.requests.Session.get")
def test_react_loop_executes_tool_then_answers(mock_get, mock_openai):
    # 模拟天气接口真实响应
    mock_get.return_value.status_code = 200
    mock_get.return_value.json.return_value = {
        "name": "Beijing",
        "main": {"temp": 25.0, "feels_like": 24.0, "humidity": 55},
        "wind": {"speed": 3.0},
        "weather": [{"description": "晴"}],
    }

    # LLM 第一轮：决定调用工具；第二轮：给出最终答案
    tool_message = SimpleNamespace(
        content=None,
        tool_calls=[_make_tool_call("get_current_weather", '{"city": "Beijing"}')],
    )
    final_message = _make_final_message("北京当前 25°C，晴，适合户外跑步。")
    fake_client = mock_openai.return_value
    fake_client.chat.completions.create.side_effect = [
        _make_response(tool_message),
        _make_response(final_message),
    ]

    agent = ReActAgent(_manager(), llm_enabled=True, openai_api_key="key")
    result = agent.run("北京现在适合跑步吗？")

    assert result["success"] is True
    assert result["answer"] == "北京当前 25°C，晴，适合户外跑步。"
    assert result["iterations"] == 2
    assert len(result["tool_calls"]) == 1
    assert result["tool_calls"][0]["tool_name"] == "get_current_weather"
    assert result["tool_calls"][0]["args"] == {"city": "Beijing"}
    assert result["tool_calls"][0]["success"] is True

    # 验证每次调用都携带了工具定义（function calling）
    _, kwargs = fake_client.chat.completions.create.call_args_list[0]
    assert "tools" in kwargs
    assert kwargs["tools"][0]["function"]["name"] == "get_current_weather"

    # 验证 tool 结果已回填到第二轮请求
    _, kwargs2 = fake_client.chat.completions.create.call_args_list[1]
    roles = [m["role"] for m in kwargs2["messages"]]
    assert roles.count("tool") == 1
    assert any(
        m["role"] == "assistant" and m.get("tool_calls") for m in kwargs2["messages"]
    )


# ----------------------------------------------------------------------
# 降级：LLM 未配置
# ----------------------------------------------------------------------
def test_react_agent_without_llm_returns_error():
    agent = ReActAgent(_manager(), llm_enabled=False)
    result = agent.run("北京天气")
    assert result["success"] is False
    assert "API Key" in result["error"]


def test_react_agent_without_api_key_returns_error():
    agent = ReActAgent(_manager(), llm_enabled=True, openai_api_key=None)
    result = agent.run("北京天气")
    assert result["success"] is False
    assert "API Key" in result["error"]


# ----------------------------------------------------------------------
# 迭代上限保护
# ----------------------------------------------------------------------
@mock.patch("app.agents.reaact_agent.OpenAI")
def test_react_agent_stops_at_max_iterations(mock_openai):
    # LLM 永远要求调用工具，Agent 应在 max_iterations 后终止
    tool_message = SimpleNamespace(
        content=None,
        tool_calls=[_make_tool_call("get_current_weather", "{}")],
    )
    fake_client = mock_openai.return_value
    fake_client.chat.completions.create.return_value = _make_response(tool_message)

    agent = ReActAgent(
        _manager(), llm_enabled=True, openai_api_key="key", max_iterations=3
    )
    result = agent.run("反复查天气")
    assert result["success"] is False
    assert "最大迭代次数" in result["error"]
    assert result["iterations"] == 3
    # 每次迭代都会执行一次工具
    assert len(result["tool_calls"]) == 3


# ----------------------------------------------------------------------
# LLM 异常兜底
# ----------------------------------------------------------------------
@mock.patch("app.agents.reaact_agent.OpenAI")
def test_react_agent_handles_llm_failure(mock_openai):
    fake_client = mock_openai.return_value
    fake_client.chat.completions.create.side_effect = RuntimeError("timeout")

    agent = ReActAgent(_manager(), llm_enabled=True, openai_api_key="key")
    result = agent.run("北京天气")
    assert result["success"] is False
    assert "LLM 调用失败" in result["error"]

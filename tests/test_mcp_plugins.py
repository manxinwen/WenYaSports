"""插件化 MCP 工具层单元测试。

覆盖：配置加载、插件启用/禁用、工具汇总、工具执行（mock API）、
加载失败隔离、健康检查。
"""

import json
from unittest import mock

import pytest

from mcp_plugins.base import BasePlugin
from mcp_plugins.manager import PluginManager


def write_config(tmp_path, plugins):
    """将插件配置写入临时文件并返回路径。"""
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"plugins": plugins}, ensure_ascii=False), encoding="utf-8")
    return str(path)


# ----------------------------------------------------------------------
# 1. 插件管理器加载（启用 weather、禁用 map_routing）
# ----------------------------------------------------------------------
def test_manager_loads_enabled_plugins_only(tmp_path):
    config_path = write_config(
        tmp_path,
        [
            {"name": "weather", "enabled": True, "config": {"api_key": "test-key"}},
            {"name": "map_routing", "enabled": False, "config": {"api_key": "x"}},
        ],
    )
    manager = PluginManager(config_path=config_path)
    plugins = manager.get_plugins()
    assert "weather" in plugins
    assert "map_routing" not in plugins
    assert isinstance(plugins["weather"], BasePlugin)


# ----------------------------------------------------------------------
# 2. get_all_tools() 返回正确工具列表
# ----------------------------------------------------------------------
def test_get_all_tools(tmp_path):
    config_path = write_config(
        tmp_path,
        [
            {"name": "weather", "enabled": True, "config": {"api_key": "test-key"}},
            {"name": "map_routing", "enabled": True, "config": {"api_key": "x"}},
        ],
    )
    manager = PluginManager(config_path=config_path)
    tools = manager.get_all_tools()

    names = {t["name"] for t in tools}
    assert names == {"get_current_weather", "get_route_profile"}

    by_name = {t["name"]: t for t in tools}
    assert by_name["get_current_weather"]["plugin"] == "weather"
    assert by_name["get_route_profile"]["plugin"] == "map_routing"
    # 工具定义需包含 JSON Schema 参数说明
    assert by_name["get_current_weather"]["parameters"]["type"] == "object"
    assert "city" in by_name["get_current_weather"]["parameters"]["properties"]
    assert by_name["get_route_profile"]["parameters"]["required"] == ["start", "end"]


# ----------------------------------------------------------------------
# 3. execute_tool() 调用天气插件（mock requests）
# ----------------------------------------------------------------------
@mock.patch(
    "mcp_plugins.plugins.weather.weather_plugin.requests.Session.get"
)
def test_execute_weather_tool_with_mock(mock_get, tmp_path):
    mock_get.return_value.status_code = 200
    mock_get.return_value.json.return_value = {
        "name": "Beijing",
        "main": {"temp": 25.0, "feels_like": 24.5, "humidity": 60},
        "wind": {"speed": 3.2},
        "weather": [{"description": "晴"}],
    }

    config_path = write_config(
        tmp_path,
        [{"name": "weather", "enabled": True, "config": {"api_key": "test-key"}}],
    )
    manager = PluginManager(config_path=config_path)

    result = manager.execute_tool("weather", "get_current_weather", {"city": "Beijing"})

    assert result["success"] is True
    assert result["temperature_c"] == 25.0
    assert result["humidity_percent"] == 60
    assert result["wind_speed_mps"] == 3.2
    assert result["description"] == "晴"
    # 确认请求参数包含城市与 api_key
    _, kwargs = mock_get.call_args
    assert kwargs["params"]["q"] == "Beijing"
    assert kwargs["params"]["appid"] == "test-key"


def test_execute_weather_without_api_key_returns_error(tmp_path):
    config_path = write_config(
        tmp_path,
        [{"name": "weather", "enabled": True, "config": {"api_key": "YOUR_API_KEY"}}],
    )
    manager = PluginManager(config_path=config_path)
    result = manager.execute_tool("weather", "get_current_weather", {})
    assert result["success"] is False
    assert "API Key" in result["error"]


def test_execute_weather_api_failure_returns_error(tmp_path):
    with mock.patch(
        "mcp_plugins.plugins.weather.weather_plugin.requests.Session.get"
    ) as mock_get:
        mock_get.side_effect = RuntimeError("connection refused")
        config_path = write_config(
            tmp_path,
            [{"name": "weather", "enabled": True, "config": {"api_key": "test-key"}}],
        )
        manager = PluginManager(config_path=config_path)
        result = manager.execute_tool("weather", "get_current_weather", {})
        assert result["success"] is False


def test_execute_unknown_plugin_returns_error(tmp_path):
    config_path = write_config(
        tmp_path,
        [{"name": "weather", "enabled": True, "config": {"api_key": "x"}}],
    )
    manager = PluginManager(config_path=config_path)
    result = manager.execute_tool("not_exists", "get_current_weather", {})
    assert result["success"] is False
    assert "未加载或不存在" in result["error"]


# ----------------------------------------------------------------------
# 4. 加载失败隔离：不存在的插件被跳过，其余正常加载
# ----------------------------------------------------------------------
def test_manager_skips_failed_plugin_and_continues(tmp_path):
    config_path = write_config(
        tmp_path,
        [
            {"name": "not_a_real_plugin", "enabled": True, "config": {}},
            {"name": "weather", "enabled": True, "config": {"api_key": "test-key"}},
        ],
    )
    manager = PluginManager(config_path=config_path)
    plugins = manager.get_plugins()
    assert "not_a_real_plugin" not in plugins
    assert "weather" in plugins


# ----------------------------------------------------------------------
# 5. health_check() 返回布尔值
# ----------------------------------------------------------------------
def test_health_check_returns_boolean(tmp_path):
    config_path = write_config(
        tmp_path,
        [{"name": "weather", "enabled": True, "config": {"api_key": "test-key"}}],
    )
    manager = PluginManager(config_path=config_path)
    checks = manager.health_checks()
    assert isinstance(checks, dict)
    assert set(checks) == {"weather"}
    for value in checks.values():
        assert isinstance(value, bool)


def test_health_check_invalid_key_returns_false(tmp_path):
    config_path = write_config(
        tmp_path,
        [{"name": "weather", "enabled": True, "config": {"api_key": "YOUR_API_KEY"}}],
    )
    manager = PluginManager(config_path=config_path)
    assert manager.health_checks()["weather"] is False


@mock.patch(
    "mcp_plugins.plugins.weather.weather_plugin.requests.Session.get"
)
def test_health_check_valid_key_with_mock(mock_get, tmp_path):
    mock_get.return_value.status_code = 200
    config_path = write_config(
        tmp_path,
        [{"name": "weather", "enabled": True, "config": {"api_key": "test-key"}}],
    )
    manager = PluginManager(config_path=config_path)
    assert manager.health_checks()["weather"] is True


# ----------------------------------------------------------------------
# 补充：模拟 MCP 协议的 handle_request 路由
# ----------------------------------------------------------------------
@mock.patch(
    "mcp_plugins.plugins.weather.weather_plugin.requests.Session.get"
)
def test_handle_request_routes_by_tool_name(mock_get, tmp_path):
    mock_get.return_value.status_code = 200
    mock_get.return_value.json.return_value = {
        "name": "Beijing",
        "main": {"temp": 20.0, "feels_like": 19.0, "humidity": 55},
        "wind": {"speed": 2.0},
        "weather": [{"description": "多云"}],
    }
    config_path = write_config(
        tmp_path,
        [{"name": "weather", "enabled": True, "config": {"api_key": "test-key"}}],
    )
    manager = PluginManager(config_path=config_path)

    result = manager.handle_request("get_current_weather", {"city": "Beijing"})
    assert result["success"] is True
    assert result["temperature_c"] == 20.0

    missing = manager.handle_request("no_such_tool", {})
    assert missing["success"] is False


# ----------------------------------------------------------------------
# 补充：地图插件工具执行与参数校验
# ----------------------------------------------------------------------
@mock.patch("mcp_plugins.plugins.map_routing.map_plugin.requests.post")
def test_execute_route_profile_with_mock(mock_post, tmp_path):
    mock_post.return_value.status_code = 200
    mock_post.return_value.json.return_value = {
        "features": [
            {
                "properties": {
                    "summary": {"distance": 10500.0, "duration": 3780.0},
                    "ascent": 120.0,
                    "descent": 95.0,
                }
            }
        ]
    }
    config_path = write_config(
        tmp_path,
        [{"name": "map_routing", "enabled": True, "config": {"api_key": "test-key"}}],
    )
    manager = PluginManager(config_path=config_path)

    result = manager.execute_tool(
        "map_routing",
        "get_route_profile",
        {"start": "116.39,39.90", "end": "116.47,39.91", "profile": "running"},
    )
    assert result["success"] is True
    assert result["distance_km"] == 10.5
    assert result["duration_min"] == 63.0
    assert result["ascent_m"] == 120.0


def test_execute_route_profile_missing_params(tmp_path):
    config_path = write_config(
        tmp_path,
        [{"name": "map_routing", "enabled": True, "config": {"api_key": "test-key"}}],
    )
    manager = PluginManager(config_path=config_path)
    result = manager.execute_tool("map_routing", "get_route_profile", {})
    assert result["success"] is False
    assert "start" in result["error"]

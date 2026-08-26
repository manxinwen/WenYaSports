"""天气查询插件：通过 OpenWeatherMap API 提供实时天气工具。

属于 MCP 工具层的示例插件，演示如何将外部 REST 服务封装为
实现 :class:`BasePlugin` 的独立插件，供上层 Agent 动态调用。
"""

import logging
from typing import Any, Dict, List, Optional

import requests

from mcp_plugins.base import BasePlugin

logger = logging.getLogger(__name__)

#: OpenWeatherMap 当前天气接口
_WEATHER_URL = "https://api.openweathermap.org/data/2.5/weather"


class WeatherPlugin(BasePlugin):
    """封装 OpenWeatherMap 当前天气查询的插件。

    配置项（来自 config.json 的 ``config`` 字段）：
    - ``api_key``: OpenWeatherMap API Key；
    - ``default_city``: 默认城市（可选，execute 未传 city 时使用）。
    """

    @property
    def name(self) -> str:
        return "weather"

    @property
    def description(self) -> str:
        return "查询指定城市（或配置默认城市）的实时天气，返回温度、湿度、风速与天气描述"

    @property
    def version(self) -> str:
        return "1.0.0"

    def __init__(self, config: Dict[str, Any]) -> None:
        self.config: Dict[str, Any] = dict(config or {})
        self._api_key: Optional[str] = self.config.get("api_key")
        self._default_city: str = self.config.get("default_city", "Beijing")
        self._session = requests.Session()
        self._session.timeout = 10  # type: ignore[attr-defined]

    # ------------------------------------------------------------------
    # 工具声明
    # ------------------------------------------------------------------
    def get_tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "get_current_weather",
                "description": (
                    "获取指定城市的实时天气，返回温度(°C)、体感温度、湿度(%)、"
                    "风速(m/s) 与天气描述。若不传 city 则使用插件配置的默认城市。"
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "city": {
                            "type": "string",
                            "description": "城市名，如 'Beijing'；可选，默认使用配置中的 default_city",
                        }
                    },
                },
            }
        ]

    # ------------------------------------------------------------------
    # 工具执行
    # ------------------------------------------------------------------
    def execute(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        if tool_name != "get_current_weather":
            return {"success": False, "error": f"weather 插件不支持的工具: {tool_name}"}

        if not self._api_key or self._api_key == "YOUR_API_KEY":
            return {
                "success": False,
                "error": "未配置有效的 OpenWeatherMap API Key，请在 config.json 中填写 api_key",
            }

        city = parameters.get("city") or self._default_city
        try:
            resp = self._session.get(
                _WEATHER_URL,
                params={"q": city, "appid": self._api_key, "units": "metric", "lang": "zh_cn"},
            )
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as exc:
            logger.warning("天气接口请求失败：%s", exc)
            return {"success": False, "error": f"天气接口请求失败：{exc}"}
        except ValueError as exc:
            logger.warning("天气接口返回非 JSON：%s", exc)
            return {"success": False, "error": f"天气接口返回格式错误：{exc}"}

        main = data.get("main", {})
        wind = data.get("wind", {})
        weather = (data.get("weather") or [{}])[0]
        return {
            "success": True,
            "city": data.get("name") or city,
            "temperature_c": main.get("temp"),
            "feels_like_c": main.get("feels_like"),
            "humidity_percent": main.get("humidity"),
            "wind_speed_mps": wind.get("speed"),
            "description": weather.get("description"),
        }

    # ------------------------------------------------------------------
    # 健康检查
    # ------------------------------------------------------------------
    def health_check(self) -> bool:
        if not self._api_key or self._api_key == "YOUR_API_KEY":
            return False
        try:
            resp = self._session.get(
                _WEATHER_URL,
                params={"q": self._default_city, "appid": self._api_key, "units": "metric"},
                timeout=5,
            )
            return resp.status_code == 200
        except requests.RequestException:
            logger.warning("天气插件健康检查失败", exc_info=True)
            return False

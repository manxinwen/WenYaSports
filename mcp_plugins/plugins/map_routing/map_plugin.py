"""地图路线查询插件：通过 OpenRouteService API 提供路线规划工具。

第二个示例插件，演示运动类型（running / cycling）相关的路线查询，
返回距离、预计时间与海拔数据，可直接服务于运动训练建议。
"""

import logging
from typing import Any, Dict, List

import requests

from mcp_plugins.base import BasePlugin

logger = logging.getLogger(__name__)

#: OpenRouteService Directions API（profile 支持 running / cycling）
_ROUTE_URL = "https://api.openrouteservice.org/v2/directions/{profile}/geojson"
#: 支持的路线计算 profile（对应不同运动类型）
_PROFILES = ("running", "cycling", "driving-car", "foot-walking")


class MapRoutingPlugin(BasePlugin):
    """封装 OpenRouteService 路线规划的插件。

    配置项：
    - ``api_key``: OpenRouteService API Key；
    - ``default_profile``: 默认运动类型（可选，默认 ``running``）。
    """

    @property
    def name(self) -> str:
        return "map_routing"

    @property
    def description(self) -> str:
        return "根据起终点坐标与运动类型计算运动路线，返回距离、预计时间与海拔数据"

    @property
    def version(self) -> str:
        return "1.0.0"

    def __init__(self, config: Dict[str, Any]) -> None:
        self.config: Dict[str, Any] = dict(config or {})
        self._api_key: str = self.config.get("api_key", "")
        self._default_profile: str = self.config.get("default_profile", "running")

    # ------------------------------------------------------------------
    # 工具声明
    # ------------------------------------------------------------------
    def get_tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "get_route_profile",
                "description": (
                    "计算从起点到终点的运动路线，返回距离(km)、预计时间(min)、"
                    "累计爬升(m) 与下降(m)。坐标格式为 '经度,纬度'，"
                    "profile 支持 running / cycling / driving-car / foot-walking。"
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "start": {
                            "type": "string",
                            "description": "起点坐标，格式 'lon,lat'，如 '116.39,39.90'",
                        },
                        "end": {
                            "type": "string",
                            "description": "终点坐标，格式 'lon,lat'，如 '116.47,39.91'",
                        },
                        "profile": {
                            "type": "string",
                            "enum": list(_PROFILES),
                            "description": "运动类型，默认 running",
                        },
                    },
                    "required": ["start", "end"],
                },
            }
        ]

    # ------------------------------------------------------------------
    # 工具执行
    # ------------------------------------------------------------------
    def execute(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        if tool_name != "get_route_profile":
            return {"success": False, "error": f"map_routing 插件不支持的工具: {tool_name}"}

        if not self._api_key or self._api_key == "YOUR_MAPBOX_TOKEN":
            return {
                "success": False,
                "error": "未配置有效的 OpenRouteService API Key，请在 config.json 中填写 api_key",
            }

        start = parameters.get("start")
        end = parameters.get("end")
        if not start or not end:
            return {"success": False, "error": "缺少必要参数 start / end"}

        profile = parameters.get("profile") or self._default_profile
        if profile not in _PROFILES:
            return {"success": False, "error": f"不支持的 profile: {profile}，可选 {list(_PROFILES)}"}

        # OpenRouteService 接收 [[lon,lat],[lon,lat],...]
        coordinates = [
            self._parse_coord(start),
            self._parse_coord(end),
        ]
        if any(c is None for c in coordinates):
            return {"success": False, "error": "坐标格式错误，应为 'lon,lat'，如 '116.39,39.90'"}

        try:
            resp = requests.post(
                _ROUTE_URL.format(profile=profile),
                json={"coordinates": coordinates},
                headers={
                    "Authorization": self._api_key,
                    "Content-Type": "application/json",
                },
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as exc:
            logger.warning("路线接口请求失败：%s", exc)
            return {"success": False, "error": f"路线接口请求失败：{exc}"}
        except ValueError as exc:
            logger.warning("路线接口返回非 JSON：%s", exc)
            return {"success": False, "error": f"路线接口返回格式错误：{exc}"}

        summary = (data.get("features") or [{}])[0].get("properties", {}).get("summary", {})
        ascent = (data.get("features") or [{}])[0].get("properties", {}).get("ascent")
        descent = (data.get("features") or [{}])[0].get("properties", {}).get("descent")

        distance_km = round(summary.get("distance", 0) / 1000.0, 2)
        duration_min = round(summary.get("duration", 0) / 60.0, 1)
        return {
            "success": True,
            "profile": profile,
            "distance_km": distance_km,
            "duration_min": duration_min,
            "ascent_m": ascent,
            "descent_m": descent,
        }

    # ------------------------------------------------------------------
    # 健康检查
    # ------------------------------------------------------------------
    def health_check(self) -> bool:
        if not self._api_key or self._api_key == "YOUR_MAPBOX_TOKEN":
            return False
        try:
            # 用一次最小化请求验证 API Key（覆盖默认 profile）
            resp = requests.post(
                _ROUTE_URL.format(profile=self._default_profile),
                json={"coordinates": [[116.39, 39.90], [116.40, 39.91]]},
                headers={
                    "Authorization": self._api_key,
                    "Content-Type": "application/json",
                },
                timeout=5,
            )
            return resp.status_code == 200
        except requests.RequestException:
            logger.warning("地图路线插件健康检查失败", exc_info=True)
            return False

    # ------------------------------------------------------------------
    # 内部工具
    # ------------------------------------------------------------------
    @staticmethod
    def _parse_coord(value: str):
        """解析 'lon,lat' 字符串为 [lon, lat] 列表，失败返回 None。"""
        parts = value.split(",")
        if len(parts) != 2:
            return None
        try:
            return [float(parts[0].strip()), float(parts[1].strip())]
        except ValueError:
            return None

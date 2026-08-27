"""运动场馆插件：查询附近健身房、跑道、游泳池等运动设施。

使用高德地图 Web API 进行 POI（Point of Interest）搜索。
支持按运动类型筛选（健身房/跑步道/游泳池/瑜伽馆等）。

配置项：
  - api_key: 高德地图 Web 服务 API Key
"""

import logging
from typing import Any, Dict, List, Optional

import requests

from mcp_plugins.base import BasePlugin

logger = logging.getLogger(__name__)

AMAP_API_BASE = "https://restapi.amap.com/v3"

# 运动场馆分类关键词
VENUE_CATEGORIES = {
    "gym": ["健身房", "fitness", "gym", "力量训练", "撸铁"],
    "running": ["跑步道", "跑道", "田径场", "塑胶跑道", "running track"],
    "pool": ["游泳池", "游泳馆", "swimming pool", "natatorium"],
    "yoga": ["瑜伽馆", "yoga", "pilates"],
    "badminton": ["羽毛球馆", "羽毛球", "badminton"],
    "basketball": ["篮球场", "篮球馆", "basketball"],
    "tennis": ["网球场", "网球馆", "tennis"],
    "cycling": ["骑行道", "自行车道", "cycling"],
    "climbing": ["攀岩馆", "攀岩", "bouldering"],
    "general": ["运动", "健身", "体育", "sports"],
}


class VenuePlugin(BasePlugin):
    """运动场馆查询插件。

    基于高德地图 API 搜索附近运动场馆，支持：
    1. 按关键词搜索（如"健身房"、"游泳池"）
    2. 按定位搜索（指定城市/经纬度）
    3. 按运动类型分类筛选
    """

    @property
    def name(self) -> str:
        return "sports_venues"

    @property
    def description(self) -> str:
        return "运动场馆插件：查询附近健身房、跑道、游泳池等运动设施"

    @property
    def version(self) -> str:
        return "1.0.0"

    def __init__(self, config: Dict[str, Any]) -> None:
        self.config = dict(config or {})
        self._api_key = self.config.get("api_key", "")
        self._default_city = self.config.get("default_city", "北京")
        self._default_radius = self.config.get("default_radius", 5000)
        self._session = requests.Session()
        self._session.timeout = 10  # type: ignore[attr-defined]

    # ------------------------------------------------------------------
    # 工具声明
    # ------------------------------------------------------------------
    def get_tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "search_venues",
                "description": "搜索指定区域内的运动场馆",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "keyword": {
                            "type": "string",
                            "description": "搜索关键词（如 健身房、游泳池、羽毛球馆）",
                        },
                        "city": {
                            "type": "string",
                            "description": "城市名，默认使用配置中的 default_city",
                        },
                        "radius": {
                            "type": "integer",
                            "description": "搜索半径（米），默认 5000",
                        },
                        "venue_type": {
                            "type": "string",
                            "description": "场馆类型: gym/running/pool/yoga/badminton/basketball/tennis/cycling/climbing/general",
                        },
                        "max_results": {
                            "type": "integer",
                            "description": "最多返回数量，默认 20",
                        },
                    },
                },
            },
            {
                "name": "get_venue_types",
                "description": "获取所有支持的场馆类型列表",
                "parameters": {"type": "object", "properties": {}},
            },
            {
                "name": "get_venue_detail",
                "description": "获取指定场馆的详细信息",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "poi_id": {
                            "type": "string",
                            "description": "POI ID",
                        },
                    },
                    "required": ["poi_id"],
                },
            },
            {
                "name": "search_nearby_by_location",
                "description": "基于经纬度搜索附近运动场馆",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "longitude": {"type": "number", "description": "经度"},
                        "latitude": {"type": "number", "description": "纬度"},
                        "keyword": {"type": "string", "description": "关键词"},
                        "radius": {"type": "integer", "description": "半径（米）"},
                    },
                    "required": ["longitude", "latitude"],
                },
            },
        ]

    # ------------------------------------------------------------------
    # 工具执行
    # ------------------------------------------------------------------
    def execute(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        dispatch = {
            "search_venues": self._search_venues,
            "get_venue_types": self._get_venue_types,
            "get_venue_detail": self._get_venue_detail,
            "search_nearby_by_location": self._search_nearby,
        }
        handler = dispatch.get(tool_name)
        if handler is None:
            return {"success": False, "error": f"venues 插件不支持的工具: {tool_name}"}

        if not self._api_key or self._api_key == "YOUR_AMAP_KEY":
            return {
                "success": False,
                "error": "未配置有效的高德地图 API Key",
            }

        try:
            return handler(parameters)
        except requests.RequestException as exc:
            return {"success": False, "error": f"地图 API 请求失败: {exc}"}
        except Exception as exc:
            return {"success": False, "error": f"执行异常: {exc}"}

    # ------------------------------------------------------------------
    # 健康检查
    # ------------------------------------------------------------------
    def health_check(self) -> bool:
        if not self._api_key:
            return False
        try:
            resp = self._session.get(
                f"{AMAP_API_BASE}/place/text",
                params={
                    "keywords": "健身房",
                    "city": self._default_city,
                    "key": self._api_key,
                    "offset": 1,
                },
                timeout=5,
            )
            data = resp.json()
            return data.get("status") == "1"
        except Exception:
            return False

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _request(self, path: str, params: Dict) -> Dict:
        """发送请求到高德地图 API。"""
        params["key"] = self._api_key
        params["output"] = "JSON"
        resp = self._session.get(
            f"{AMAP_API_BASE}{path}", params=params, timeout=10
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") != "1":
            raise ValueError(f"高德 API 错误: {data.get('info')}")
        return data

    # ------------------------------------------------------------------
    # 工具实现
    # ------------------------------------------------------------------

    def _search_venues(self, params: Dict) -> Dict:
        keyword = params.get("keyword", "运动")
        city = params.get("city", self._default_city)
        radius = params.get("radius", self._default_radius)
        venue_type = params.get("venue_type")
        max_results = min(params.get("max_results", 20), 50)

        # 如果指定了场馆类型，自动补充关键词
        if venue_type and venue_type in VENUE_CATEGORIES:
            keywords = VENUE_CATEGORIES[venue_type]
            # 使用第一个关键词作为主要搜索词
            search_keyword = keywords[0]
            if keyword == "运动":  # 默认值，替换为类型关键词
                keyword = search_keyword

        # 使用文本搜索 API
        data = self._request(
            "/place/text",
            params={
                "keywords": keyword,
                "city": city,
                "offset": max_results,
                "extensions": "base",
            },
        )

        venues = []
        for poi in data.get("pois", []):
            venue = {
                "id": poi.get("id"),
                "name": poi.get("name"),
                "address": poi.get("address"),
                "city": poi.get("cityname"),
                "district": poi.get("adname"),
                "location": poi.get("location"),
                "tel": poi.get("tel"),
                "type": poi.get("type"),
                "rating": poi.get("biz_ext", {}).get("rating") if poi.get("biz_ext") else None,
                "cost": poi.get("biz_ext", {}).get("cost") if poi.get("biz_ext") else None,
            }
            venues.append(venue)

        # 按类型过滤（如果指定了 venue_type）
        if venue_type and venue_type in VENUE_CATEGORIES:
            keywords_to_match = [kw.lower() for kw in VENUE_CATEGORIES[venue_type]]
            filtered = []
            for v in venues:
                text = f"{v['name']} {v.get('type', '')} {v.get('address', '')}".lower()
                if any(kw in text for kw in keywords_to_match):
                    filtered.append(v)
            venues = filtered[:max_results]

        return {
            "success": True,
            "keyword": keyword,
            "city": city,
            "count": len(venues),
            "venues": venues,
        }

    def _get_venue_types(self, params: Dict) -> Dict:
        types = []
        for key, keywords in VENUE_CATEGORIES.items():
            types.append({
                "id": key,
                "keywords": keywords[:3],
            })
        return {
            "success": True,
            "types": types,
        }

    def _get_venue_detail(self, params: Dict) -> Dict:
        poi_id = params.get("poi_id")
        if not poi_id:
            return {"success": False, "error": "poi_id 必填"}

        data = self._request(
            "/place/detail",
            params={"id": poi_id, "extensions": "base"},
        )

        pois = data.get("pois", [])
        if not pois:
            return {"success": False, "error": "未找到该场馆"}

        poi = pois[0]
        return {
            "success": True,
            "detail": {
                "id": poi.get("id"),
                "name": poi.get("name"),
                "address": poi.get("address"),
                "location": poi.get("location"),
                "tel": poi.get("tel"),
                "type": poi.get("type"),
                "rating": poi.get("biz_ext", {}).get("rating") if poi.get("biz_ext") else None,
                "cost": poi.get("biz_ext", {}).get("cost") if poi.get("biz_ext") else None,
                "open_time": poi.get("biz_ext", {}).get("open_time") if poi.get("biz_ext") else None,
                "photos": poi.get("photos", [])[:3] if poi.get("photos") else [],
            },
        }

    def _search_nearby(self, params: Dict) -> Dict:
        lng = params.get("longitude")
        lat = params.get("latitude")
        if not lng or not lat:
            return {"success": False, "error": "longitude 和 latitude 必填"}

        keyword = params.get("keyword", "运动")
        radius = params.get("radius", self._default_radius)

        data = self._request(
            "/place/around",
            params={
                "location": f"{lng},{lat}",
                "keywords": keyword,
                "radius": radius,
                "offset": 20,
            },
        )

        venues = []
        for poi in data.get("pois", []):
            venues.append({
                "id": poi.get("id"),
                "name": poi.get("name"),
                "address": poi.get("address"),
                "distance": poi.get("distance"),
                "location": poi.get("location"),
                "type": poi.get("type"),
            })

        return {
            "success": True,
            "center": {"longitude": lng, "latitude": lat},
            "count": len(venues),
            "venues": venues,
        }

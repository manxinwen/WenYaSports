"""Strava 运动数据插件：通过 Strava API v3 读取运动员活动数据。

支持功能：
  1. 获取个人资料和统计数据
  2. 列出近期活动（支持时间范围过滤）
  3. 获取活动详情（含心率/配速/海拔等指标）
  4. 获取活动时间流数据（HR/配速/功率/步频）
  5. 获取装备里程统计
  6. OAuth2 自动 token 刷新

配置项（来自 config.json）：
  - client_id: Strava App Client ID
  - client_secret: Strava App Client Secret
  - access_token: 访问令牌（6小时过期）
  - refresh_token: 刷新令牌（自动续期）
  - auto_refresh: 是否自动刷新过期 token
"""

import logging
import time
from typing import Any, Dict, List, Optional

import requests

from mcp_plugins.base import BasePlugin

logger = logging.getLogger(__name__)

STRAVA_API_BASE = "https://www.strava.com/api/v3"
STRAVA_TOKEN_URL = "https://www.strava.com/oauth/token"


class StravaPlugin(BasePlugin):
    """Strava 运动数据 API 插件。

    将 Strava 的 REST API 封装为 MCP 工具，供 Agent 调用。
    """

    @property
    def name(self) -> str:
        return "strava"

    @property
    def description(self) -> str:
        return "Strava 运动数据插件：读取运动员的活动、统计、装备等数据"

    @property
    def version(self) -> str:
        return "1.0.0"

    def __init__(self, config: Dict[str, Any]) -> None:
        self.config = dict(config or {})
        self._client_id = self.config.get("client_id", "")
        self._client_secret = self.config.get("client_secret", "")
        self._access_token = self.config.get("access_token", "")
        self._refresh_token = self.config.get("refresh_token", "")
        self._auto_refresh = self.config.get("auto_refresh", True)
        self._token_expires_at = self.config.get("token_expires_at", 0)
        self._session = requests.Session()
        self._session.timeout = 15  # type: ignore[attr-defined]

    # ------------------------------------------------------------------
    # 工具声明
    # ------------------------------------------------------------------
    def get_tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "get_athlete_profile",
                "description": "获取已认证运动员的基本资料（姓名、城市、体重等）",
                "parameters": {"type": "object", "properties": {}},
            },
            {
                "name": "get_athlete_stats",
                "description": "获取运动员累计统计（总里程、活动次数、总时长）",
                "parameters": {"type": "object", "properties": {}},
            },
            {
                "name": "list_activities",
                "description": "列出近期活动，支持按天数、数量过滤",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "days": {
                            "type": "integer",
                            "description": "获取最近 N 天的活动，默认 14",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "最多返回数量，默认 30，最大 200",
                        },
                        "sport_type": {
                            "type": "string",
                            "description": "按运动类型过滤（Run/Ride/Swim/Hike 等）",
                        },
                    },
                },
            },
            {
                "name": "get_activity_detail",
                "description": "获取活动详情，包含距离、配速、心率、海拔、卡路里等指标",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "activity_id": {
                            "type": "integer",
                            "description": "活动 ID",
                        },
                        "include_stream": {
                            "type": "boolean",
                            "description": "是否包含时间流数据（HR/配速/功率），默认 false",
                        },
                    },
                    "required": ["activity_id"],
                },
            },
            {
                "name": "get_activity_streams",
                "description": "获取活动的时间流数据（秒级心率/配速/功率/海拔）",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "activity_id": {
                            "type": "integer",
                            "description": "活动 ID",
                        },
                        "keys": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "数据类型: time/distance/heartrate/cadence/watts/altitude/velocity_smooth",
                        },
                    },
                    "required": ["activity_id"],
                },
            },
            {
                "name": "get_gear_mileage",
                "description": "获取所有装备（跑鞋/自行车）的累计里程",
                "parameters": {"type": "object", "properties": {}},
            },
            {
                "name": "sync_to_activities",
                "description": "将 Strava 活动数据同步到 WenYaSports 系统",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "days": {
                            "type": "integer",
                            "description": "同步最近 N 天的活动",
                        },
                    },
                },
            },
        ]

    # ------------------------------------------------------------------
    # 工具执行
    # ------------------------------------------------------------------
    def execute(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        # 自动刷新 token
        if self._auto_refresh and self._is_token_expired():
            self._refresh_access_token()

        dispatch = {
            "get_athlete_profile": self._get_athlete_profile,
            "get_athlete_stats": self._get_athlete_stats,
            "list_activities": self._list_activities,
            "get_activity_detail": self._get_activity_detail,
            "get_activity_streams": self._get_activity_streams,
            "get_gear_mileage": self._get_gear_mileage,
            "sync_to_activities": self._sync_to_activities,
        }
        handler = dispatch.get(tool_name)
        if handler is None:
            return {"success": False, "error": f"strava 插件不支持的工具: {tool_name}"}

        if not self._access_token:
            return {
                "success": False,
                "error": "未配置 access_token，请先在 Strava 创建 App 并完成 OAuth 授权",
            }

        try:
            return handler(parameters)
        except requests.RequestException as exc:
            logger.warning("Strava API 请求失败: %s", exc)
            return {"success": False, "error": f"Strava API 请求失败: {exc}"}
        except Exception as exc:
            logger.exception("Strava 插件执行异常")
            return {"success": False, "error": f"执行异常: {exc}"}

    # ------------------------------------------------------------------
    # 健康检查
    # ------------------------------------------------------------------
    def health_check(self) -> bool:
        if not self._access_token:
            return False
        try:
            self._request("GET", "/athlete")
            return True
        except Exception:
            return False

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _is_token_expired(self) -> bool:
        """检查 access_token 是否过期。"""
        if self._token_expires_at <= 0:
            return False
        # 提前 60 秒刷新
        return time.time() >= self._token_expires_at - 60

    def _refresh_access_token(self) -> None:
        """使用 refresh_token 刷新 access_token。"""
        if not self._refresh_token or not self._client_id or not self._client_secret:
            logger.warning("缺少 refresh_token 或 client 配置，跳过 token 刷新")
            return

        try:
            resp = self._session.post(
                STRAVA_TOKEN_URL,
                data={
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                    "grant_type": "refresh_token",
                    "refresh_token": self._refresh_token,
                },
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
            self._access_token = data.get("access_token", self._access_token)
            self._refresh_token = data.get("refresh_token", self._refresh_token)
            self._token_expires_at = time.time() + data.get("expires_in", 21600)
            self.config["access_token"] = self._access_token
            self.config["refresh_token"] = self._refresh_token
            self.config["token_expires_at"] = self._token_expires_at
            logger.info("Strava token 刷新成功")
        except Exception as exc:
            logger.warning("Strava token 刷新失败: %s", exc)

    def _request(
        self, method: str, path: str, params: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """发送请求到 Strava API。"""
        url = f"{STRAVA_API_BASE}{path}"
        headers = {"Authorization": f"Bearer {self._access_token}"}
        resp = self._session.request(
            method, url, headers=headers, params=params, timeout=15
        )
        if resp.status_code == 401:
            # Token 过期，尝试刷新后重试
            if self._auto_refresh:
                self._refresh_access_token()
                headers = {"Authorization": f"Bearer {self._access_token}"}
                resp = self._session.request(
                    method, url, headers=headers, params=params, timeout=15
                )
        resp.raise_for_status()
        return resp.json()

    # ------------------------------------------------------------------
    # 工具实现
    # ------------------------------------------------------------------

    def _get_athlete_profile(self, params: Dict) -> Dict:
        data = self._request("GET", "/athlete")
        return {
            "success": True,
            "athlete_id": data.get("id"),
            "firstname": data.get("firstname"),
            "lastname": data.get("lastname"),
            "city": data.get("city"),
            "country": data.get("country"),
            "sex": data.get("sex"),
            "weight": data.get("weight"),
            "height": data.get("height"),
            "premium": data.get("premium"),
            "created_at": data.get("created_at"),
            "follower_count": data.get("follower_count"),
            "friend_count": data.get("friend_count"),
        }

    def _get_athlete_stats(self, params: Dict) -> Dict:
        athlete_data = self._request("GET", "/athlete")
        athlete_id = athlete_data.get("id")
        if athlete_id is None:
            return {"success": False, "error": "无法获取运动员 ID"}

        stats = self._request("GET", f"/athletes/{athlete_id}/stats")
        return {
            "success": True,
            "athlete_id": athlete_id,
            "recent_run_totals": stats.get("recent_run_totals"),
            "recent_ride_totals": stats.get("recent_ride_totals"),
            "ytd_run_totals": stats.get("ytd_run_totals"),
            "ytd_ride_totals": stats.get("ytd_ride_totals"),
            "all_run_totals": stats.get("all_run_totals"),
            "all_ride_totals": stats.get("all_ride_totals"),
        }

    def _list_activities(self, params: Dict) -> Dict:
        days = params.get("days", 14)
        limit = min(params.get("limit", 30), 200)
        sport_type = params.get("sport_type")

        after_ts = int(time.time()) - days * 86400
        all_activities = []
        page = 1

        while len(all_activities) < limit:
            batch = self._request(
                "GET",
                "/athlete/activities",
                params={
                    "after": after_ts,
                    "page": page,
                    "per_page": min(50, limit - len(all_activities)),
                },
            )
            if not batch:
                break
            for act in batch:
                if sport_type and act.get("sport_type") != sport_type:
                    continue
                all_activities.append({
                    "id": act.get("id"),
                    "name": act.get("name"),
                    "sport_type": act.get("sport_type"),
                    "distance_m": act.get("distance"),
                    "moving_time_s": act.get("moving_time"),
                    "elapsed_time_s": act.get("elapsed_time"),
                    "total_elevation_gain_m": act.get("total_elevation_gain"),
                    "average_speed_ms": act.get("average_speed"),
                    "max_speed_ms": act.get("max_speed"),
                    "average_heartrate": act.get("average_heartrate"),
                    "max_heartrate": act.get("max_heartrate"),
                    "average_cadence": act.get("average_cadence"),
                    "average_watts": act.get("average_watts"),
                    "calories": act.get("calories"),
                    "start_date_local": act.get("start_date_local"),
                    "description": act.get("description"),
                    "gear_id": act.get("gear_id"),
                })
                if len(all_activities) >= limit:
                    break
            page += 1

        return {
            "success": True,
            "count": len(all_activities),
            "days_filter": days,
            "activities": all_activities,
        }

    def _get_activity_detail(self, params: Dict) -> Dict:
        activity_id = params.get("activity_id")
        if not activity_id:
            return {"success": False, "error": "activity_id 必填"}

        data = self._request("GET", f"/activities/{activity_id}")
        result = {
            "success": True,
            "id": data.get("id"),
            "name": data.get("name"),
            "sport_type": data.get("sport_type"),
            "distance_m": data.get("distance"),
            "moving_time_s": data.get("moving_time"),
            "elapsed_time_s": data.get("elapsed_time"),
            "total_elevation_gain_m": data.get("total_elevation_gain"),
            "average_speed_ms": data.get("average_speed"),
            "max_speed_ms": data.get("max_speed"),
            "average_heartrate": data.get("average_heartrate"),
            "max_heartrate": data.get("max_heartrate"),
            "average_cadence": data.get("average_cadence"),
            "average_watts": data.get("average_watts"),
            "calories": data.get("calories"),
            "start_date_local": data.get("start_date_local"),
            "description": data.get("description"),
            "has_heartrate": data.get("has_heartrate"),
            "has_kudo_pr": data.get("has_kudo_pr"),
            "pr_count": data.get("pr_count"),
            "gear": data.get("gear"),
            "splits_metric": data.get("splits_metric"),
            "laps": data.get("laps"),
        }

        # 可选获取时间流
        if params.get("include_stream"):
            try:
                streams = self._request(
                    "GET",
                    f"/activities/{activity_id}/streams",
                    params={
                        "keys": "heartrate,cadence,watts,velocity_smooth,altitude",
                        "key_by_type": "true",
                    },
                )
                result["streams"] = streams
            except Exception as e:
                result["stream_error"] = str(e)

        return result

    def _get_activity_streams(self, params: Dict) -> Dict:
        activity_id = params.get("activity_id")
        if not activity_id:
            return {"success": False, "error": "activity_id 必填"}

        keys = params.get("keys") or [
            "heartrate", "cadence", "watts", "velocity_smooth", "altitude"
        ]
        keys_str = ",".join(keys)

        streams = self._request(
            "GET",
            f"/activities/{activity_id}/streams",
            params={"keys": keys_str, "key_by_type": "true"},
        )
        return {
            "success": True,
            "activity_id": activity_id,
            "streams": streams,
        }

    def _get_gear_mileage(self, params: Dict) -> Dict:
        athlete_data = self._request("GET", "/athlete")
        athlete_id = athlete_data.get("id")
        if athlete_id is None:
            return {"success": False, "error": "无法获取运动员 ID"}

        gear_list = self._request(
            "GET", f"/athletes/{athlete_id}/gear"
        )
        results = []
        for gear in gear_list:
            results.append({
                "id": gear.get("id"),
                "name": gear.get("name"),
                "brand_name": gear.get("brand_name"),
                "model_name": gear.get("model_name"),
                "distance_m": gear.get("distance"),
                "distance_km": round(gear.get("distance", 0) / 1000, 2),
                "type": gear.get("type"),
                "retired": gear.get("retired"),
            })

        return {
            "success": True,
            "gear_count": len(results),
            "gear": results,
        }

    def _sync_to_activities(self, params: Dict) -> Dict:
        """将 Strava 活动同步到 WenYaSports 活动数据库。"""
        days = params.get("days", 30)
        activities_result = self._list_activities({"days": days, "limit": 200})

        if not activities_result.get("success"):
            return activities_result

        synced = 0
        skipped = 0
        errors = []

        for act in activities_result.get("activities", []):
            try:
                # 这里可以接入 WenYaSports 的活动数据库
                # 将 Strava 数据转换为 WenYaSports 的活动格式
                from app.db import database

                # 检查是否已存在（通过 Strava 活动 ID 在 metadata 中判断）
                # 简化处理：直接存入
                import json
                database.insert_activity(
                    user_id="strava_user",
                    date=act.get("start_date_local", "")[:10],
                    features_json=json.dumps({
                        "source": "strava",
                        "strava_id": act.get("id"),
                        "sport_type": act.get("sport_type"),
                        "distance_m": act.get("distance_m"),
                        "moving_time_s": act.get("moving_time_s"),
                        "average_heartrate": act.get("average_heartrate"),
                        "average_speed_ms": act.get("average_speed_ms"),
                        "total_elevation_gain_m": act.get("total_elevation_gain_m"),
                    }),
                    metadata_json=json.dumps({
                        "source": "strava_api",
                        "activity_name": act.get("name"),
                        "start_date": act.get("start_date_local"),
                    }),
                )
                synced += 1
            except Exception as e:
                skipped += 1
                errors.append(f"{act.get('id')}: {str(e)}")

        return {
            "success": True,
            "synced": synced,
            "skipped": skipped,
            "errors": errors,
            "days": days,
        }

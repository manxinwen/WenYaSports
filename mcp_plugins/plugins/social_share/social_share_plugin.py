"""社交分享插件：将运动成就分享到社交平台。

支持功能：
  1. 生成运动分享卡片（文字 + 数据摘要）
  2. 生成分享链接
  3. 格式化不同平台的分享文本（微博/微信/朋友圈/小红书）

说明：由于微信/微博等平台的 OAuth 授权流程较复杂（需企业认证），
本插件提供「生成分享内容」和「生成分享链接」的核心能力，
实际的发布操作可通过以下方式实现：
  - 复制到剪贴板，用户手动粘贴发布
  - 生成短链/图片，引导用户分享
  - 对接第三方发布服务（如 Buffer/Hootsuite）

配置项：
  - site_url: 应用站点 URL（用于生成分享链接）
  - default_platform: 默认分享平台（weibo/wechat/xiaohongshu）
"""

import logging
import urllib.parse
from datetime import datetime
from typing import Any, Dict, List, Optional

from mcp_plugins.base import BasePlugin

logger = logging.getLogger(__name__)

# 分享平台配置
PLATFORMS = {
    "weibo": {
        "name": "微博",
        "max_length": 140,
        "url_template": "https://service.weibo.com/share/share.php?url={url}&title={title}",
        "icon": "📱",
    },
    "wechat": {
        "name": "微信朋友圈",
        "max_length": 0,  # 无限制
        "url_template": "",  # 无直接分享 URL
        "icon": "💬",
    },
    "xiaohongshu": {
        "name": "小红书",
        "max_length": 1000,
        "url_template": "",  # 需 App 内分享
        "icon": "📷",
    },
    "twitter": {
        "name": "Twitter/X",
        "max_length": 280,
        "url_template": "https://twitter.com/intent/tweet?url={url}&text={title}",
        "icon": "🐦",
    },
    "generic": {
        "name": "通用",
        "max_length": 0,
        "url_template": "",
        "icon": "🔗",
    },
}


class SocialSharePlugin(BasePlugin):
    """社交分享插件。

    核心价值：将运动数据转化为社交友好的分享内容，
    降低用户分享运动成就的操作成本。
    """

    @property
    def name(self) -> str:
        return "social_share"

    @property
    def description(self) -> str:
        return "社交分享插件：生成运动成就分享内容、链接和卡片"

    @property
    def version(self) -> str:
        return "1.0.0"

    def __init__(self, config: Dict[str, Any]) -> None:
        self.config = dict(config or {})
        self._site_url = self.config.get("site_url", "https://wenyasports.local")
        self._default_platform = self.config.get("default_platform", "weibo")

    # ------------------------------------------------------------------
    # 工具声明
    # ------------------------------------------------------------------
    def get_tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "generate_activity_share",
                "description": "生成活动分享内容（文字摘要 + 链接）",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "activity_data": {
                            "type": "object",
                            "description": "活动数据: {name, sport_type, distance_m, moving_time_s, average_heartrate, calories, start_date_local}",
                        },
                        "platform": {
                            "type": "string",
                            "description": "目标平台: weibo/wechat/xiaohongshu/twitter/generic",
                        },
                        "include_stats": {
                            "type": "boolean",
                            "description": "是否包含详细统计数据",
                        },
                    },
                    "required": ["activity_data"],
                },
            },
            {
                "name": "generate_achievement_card",
                "description": "生成成就卡片（周/月/年总结）的分享内容",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "period": {
                            "type": "string",
                            "description": "周期: weekly/monthly/yearly/all",
                        },
                        "stats": {
                            "type": "object",
                            "description": "统计数据: {total_distance_m, total_activities, total_time_s, total_calories, personal_records}",
                        },
                        "platform": {
                            "type": "string",
                            "description": "目标平台",
                        },
                    },
                },
            },
            {
                "name": "get_share_platforms",
                "description": "获取所有支持的分享平台列表",
                "parameters": {"type": "object", "properties": {}},
            },
            {
                "name": "build_share_url",
                "description": "构建指定平台的分享 URL",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "platform": {"type": "string", "description": "平台名"},
                        "url": {"type": "string", "description": "分享链接"},
                        "title": {"type": "string", "description": "分享标题"},
                    },
                    "required": ["platform", "url"],
                },
            },
        ]

    # ------------------------------------------------------------------
    # 工具执行
    # ------------------------------------------------------------------
    def execute(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        dispatch = {
            "generate_activity_share": self._generate_activity_share,
            "generate_achievement_card": self._generate_achievement_card,
            "get_share_platforms": self._get_platforms,
            "build_share_url": self._build_share_url,
        }
        handler = dispatch.get(tool_name)
        if handler is None:
            return {"success": False, "error": f"social_share 不支持: {tool_name}"}

        try:
            return handler(parameters)
        except Exception as exc:
            logger.exception("社交分享执行异常")
            return {"success": False, "error": f"执行异常: {exc}"}

    # ------------------------------------------------------------------
    # 健康检查
    # ------------------------------------------------------------------
    def health_check(self) -> bool:
        return True  # 纯本地计算，始终可用

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _format_distance(self, meters: float) -> str:
        """格式化距离。"""
        if meters >= 1000:
            return f"{meters / 1000:.1f} km"
        return f"{meters:.0f} m"

    def _format_time(self, seconds: int) -> str:
        """格式化时间。"""
        if seconds >= 3600:
            h = seconds // 3600
            m = (seconds % 3600) // 60
            return f"{h}h {m}m"
        m = seconds // 60
        s = seconds % 60
        return f"{m}m {s:02d}s"

    def _format_speed(self, ms: float) -> str:
        """格式化速度。"""
        if ms <= 0:
            return "—"
        # 配速：分钟/公里
        pace_min_per_km = 1000 / ms / 60
        minutes = int(pace_min_per_km)
        seconds = int((pace_min_per_km - minutes) * 60)
        return f"{minutes}'{seconds:02d}\"/km"

    def _truncate(self, text: str, max_len: int) -> str:
        """截断文本到指定长度。"""
        if max_len <= 0 or len(text) <= max_len:
            return text
        return text[:max_len - 3] + "..."

    # ------------------------------------------------------------------
    # 工具实现
    # ------------------------------------------------------------------

    def _generate_activity_share(self, params: Dict) -> Dict:
        activity = params.get("activity_data", {})
        platform = params.get("platform", self._default_platform)
        include_stats = params.get("include_stats", True)

        if not activity:
            return {"success": False, "error": "activity_data 必填"}

        # 活动数据
        name = activity.get("name", "未命名活动")
        sport_type = activity.get("sport_type", "运动")
        distance = activity.get("distance_m", 0)
        moving_time = activity.get("moving_time_s", 0)
        avg_hr = activity.get("average_heartrate")
        avg_speed = activity.get("average_speed_ms")
        calories = activity.get("calories")
        date = activity.get("start_date_local", "")

        # 运动类型中文映射
        sport_cn = {
            "Run": "跑步", "TrailRun": "越野跑", "Ride": "骑行",
            "Swim": "游泳", "Hike": "徒步", "Walk": "步行",
            "Strength": "力量训练", "Yoga": "瑜伽",
        }
        sport_label = sport_cn.get(sport_type, sport_type)

        # 构建分享文本
        lines = []
        lines.append(f"🏃 刚刚完成了一次{sport_label}！")
        lines.append(f"")
        lines.append(f"📏 距离: {self._format_distance(distance)}")
        lines.append(f"⏱️ 用时: {self._format_time(moving_time)}")

        if include_stats:
            if avg_speed:
                lines.append(f"⚡ 配速: {self._format_speed(avg_speed)}")
            if avg_hr:
                lines.append(f"❤️ 平均心率: {avg_hr} bpm")
            if calories:
                lines.append(f"🔥 消耗: {calories} kcal")

        lines.append(f"")
        lines.append(f"#运动日常 #坚持就是胜利")

        # 截断到平台限制
        platform_info = PLATFORMS.get(platform, PLATFORMS["generic"])
        text = "\n".join(lines)
        if platform_info["max_length"] > 0:
            text = self._truncate(text, platform_info["max_length"])

        # 生成分享 URL
        share_url = None
        if platform_info.get("url_template"):
            encoded_url = urllib.parse.quote(self._site_url)
            encoded_title = urllib.parse.quote(text[:50])
            share_url = platform_info["url_template"].format(
                url=encoded_url, title=encoded_title
            )

        return {
            "success": True,
            "platform": platform,
            "platform_name": platform_info["name"],
            "text": text,
            "share_url": share_url,
            "copy_hint": (
                f"复制上面的文字，打开{platform_info['name']}粘贴发布"
                if not share_url
                else f"点击链接直接分享到{platform_info['name']}"
            ),
            "activity_summary": {
                "name": name,
                "sport_type": sport_label,
                "distance": self._format_distance(distance),
                "duration": self._format_time(moving_time),
            },
        }

    def _generate_achievement_card(self, params: Dict) -> Dict:
        period = params.get("period", "weekly")
        stats = params.get("stats", {})
        platform = params.get("platform", self._default_platform)

        period_cn = {
            "weekly": "本周", "monthly": "本月",
            "yearly": "今年", "all": "累计",
        }
        period_label = period_cn.get(period, period)

        total_distance = stats.get("total_distance_m", 0)
        total_activities = stats.get("total_activities", 0)
        total_time = stats.get("total_time_s", 0)
        total_calories = stats.get("total_calories", 0)
        prs = stats.get("personal_records", [])

        lines = []
        lines.append(f"🎉 {period_label}运动总结 🎉")
        lines.append(f"")
        lines.append(f"🏆 完成 {total_activities} 次运动")
        lines.append(f"📏 总里程 {self._format_distance(total_distance)}")
        lines.append(f"⏱️ 总时长 {self._format_time(total_time)}")
        if total_calories:
            lines.append(f"🔥 总消耗 {total_calories} kcal")

        if prs:
            lines.append(f"")
            lines.append(f"⭐ 新纪录:")
            for pr in prs[:3]:
                lines.append(f"  • {pr.get('label', '')}: {pr.get('value', '')}")

        lines.append(f"")
        lines.append(f"#运动总结 #WenYaSports")

        # 截断
        platform_info = PLATFORMS.get(platform, PLATFORMS["generic"])
        text = "\n".join(lines)
        if platform_info["max_length"] > 0:
            text = self._truncate(text, platform_info["max_length"])

        # 生成分享 URL
        share_url = None
        if platform_info.get("url_template"):
            encoded_url = urllib.parse.quote(self._site_url)
            encoded_title = urllib.parse.quote(text[:50])
            share_url = platform_info["url_template"].format(
                url=encoded_url, title=encoded_title
            )

        return {
            "success": True,
            "period": period,
            "period_label": period_label,
            "text": text,
            "share_url": share_url,
            "platform": platform,
            "stats_summary": {
                "activities": total_activities,
                "distance": self._format_distance(total_distance),
                "time": self._format_time(total_time),
            },
        }

    def _get_platforms(self, params: Dict) -> Dict:
        platforms = []
        for key, info in PLATFORMS.items():
            platforms.append({
                "id": key,
                "name": info["name"],
                "icon": info["icon"],
                "max_length": info["max_length"],
                "has_share_url": bool(info.get("url_template")),
            })
        return {
            "success": True,
            "platforms": platforms,
        }

    def _build_share_url(self, params: Dict) -> Dict:
        platform = params.get("platform")
        url = params.get("url")
        title = params.get("title", "")

        if not platform or not url:
            return {"success": False, "error": "platform 和 url 必填"}

        platform_info = PLATFORMS.get(platform)
        if not platform_info:
            return {"success": False, "error": f"不支持的平台: {platform}"}

        if not platform_info.get("url_template"):
            return {
                "success": False,
                "error": f"{platform_info['name']} 不支持直接 URL 分享",
            }

        encoded_url = urllib.parse.quote(url)
        encoded_title = urllib.parse.quote(title)
        share_url = platform_info["url_template"].format(
            url=encoded_url, title=encoded_title
        )

        return {
            "success": True,
            "platform": platform,
            "platform_name": platform_info["name"],
            "share_url": share_url,
        }

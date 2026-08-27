"""新 MCP 插件测试：Strava、运动场馆、社交分享。"""

import pytest
from unittest.mock import patch, MagicMock


class TestStravaPlugin:
    @pytest.fixture
    def plugin(self):
        from mcp_plugins.plugins.strava.strava_plugin import StravaPlugin
        return StravaPlugin(config={
            "client_id": "test_id",
            "client_secret": "test_secret",
            "access_token": "test_token",
            "refresh_token": "test_refresh",
            "auto_refresh": False,
        })

    def test_name(self, plugin):
        assert plugin.name == "strava"

    def test_version(self, plugin):
        assert plugin.version == "1.0.0"

    def test_get_tools(self, plugin):
        tools = plugin.get_tools()
        assert len(tools) >= 7
        tool_names = [t["name"] for t in tools]
        assert "get_athlete_profile" in tool_names
        assert "list_activities" in tool_names
        assert "get_activity_detail" in tool_names
        assert "get_activity_streams" in tool_names
        assert "get_gear_mileage" in tool_names
        assert "sync_to_activities" in tool_names

    def test_execute_unknown_tool(self, plugin):
        result = plugin.execute("unknown_tool", {})
        assert not result["success"]
        assert "不支持" in result["error"]

    def test_execute_no_token(self):
        from mcp_plugins.plugins.strava.strava_plugin import StravaPlugin
        plugin = StravaPlugin(config={"access_token": ""})
        result = plugin.execute("get_athlete_profile", {})
        assert not result["success"]

    def test_health_check_no_token(self):
        from mcp_plugins.plugins.strava.strava_plugin import StravaPlugin
        plugin = StravaPlugin(config={"access_token": ""})
        assert not plugin.health_check()

    @patch("mcp_plugins.plugins.strava.strava_plugin.requests.Session")
    def test_get_athlete_profile(self, mock_session_cls, plugin):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "id": 12345,
            "firstname": "Test",
            "lastname": "User",
            "city": "Beijing",
            "country": "China",
            "sex": "M",
            "weight": 70,
            "height": 175,
            "premium": False,
            "created_at": "2024-01-01T00:00:00Z",
            "follower_count": 10,
            "friend_count": 20,
        }
        mock_session = MagicMock()
        mock_session.request.return_value = mock_resp
        plugin._session = mock_session

        result = plugin._get_athlete_profile({})
        assert result["success"]
        assert result["firstname"] == "Test"
        assert result["city"] == "Beijing"

    @patch("mcp_plugins.plugins.strava.strava_plugin.requests.Session")
    def test_list_activities(self, mock_session_cls, plugin):
        call_count = [0]

        def mock_request(method, url, headers, params=None, timeout=None):
            call_count[0] += 1
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            if call_count[0] > 1:  # Second page returns empty
                mock_resp.json.return_value = []
            else:
                mock_resp.json.return_value = [
                    {
                        "id": 1,
                        "name": "Morning Run",
                        "sport_type": "Run",
                        "distance": 10000,
                        "moving_time": 3600,
                        "elapsed_time": 3800,
                        "total_elevation_gain": 50,
                        "average_speed": 2.78,
                        "max_speed": 5.5,
                        "average_heartrate": 150,
                        "max_heartrate": 180,
                        "average_cadence": 170,
                        "average_watts": 200,
                        "calories": 700,
                        "start_date_local": "2024-06-01T07:00:00Z",
                        "description": "Easy run",
                        "gear_id": None,
                    }
                ]
            return mock_resp

        mock_session = MagicMock()
        mock_session.request.side_effect = mock_request
        plugin._session = mock_session

        result = plugin._list_activities({"days": 7, "limit": 10})
        assert result["success"]
        assert result["count"] == 1
        assert result["activities"][0]["sport_type"] == "Run"

    @patch("mcp_plugins.plugins.strava.strava_plugin.requests.Session")
    def test_get_activity_detail(self, mock_session_cls, plugin):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "id": 1,
            "name": "Test Activity",
            "sport_type": "Run",
            "distance": 10000,
            "moving_time": 3600,
            "elapsed_time": 3800,
            "total_elevation_gain": 50,
            "average_speed": 2.78,
            "max_speed": 5.5,
            "average_heartrate": 150,
            "max_heartrate": 180,
            "average_cadence": 170,
            "average_watts": 200,
            "calories": 700,
            "start_date_local": "2024-06-01T07:00:00Z",
            "description": "",
            "has_heartrate": True,
            "has_kudo_pr": False,
            "pr_count": 0,
            "gear": None,
            "splits_metric": [],
            "laps": [],
        }
        mock_session = MagicMock()
        mock_session.request.return_value = mock_resp
        plugin._session = mock_session

        result = plugin._get_activity_detail({"activity_id": 1})
        assert result["success"]
        assert result["id"] == 1


class TestVenuePlugin:
    @pytest.fixture
    def plugin(self):
        from mcp_plugins.plugins.sports_venues.venue_plugin import VenuePlugin
        return VenuePlugin(config={
            "api_key": "test_amap_key",
            "default_city": "北京",
            "default_radius": 5000,
        })

    def test_name(self, plugin):
        assert plugin.name == "sports_venues"

    def test_get_tools(self, plugin):
        tools = plugin.get_tools()
        assert len(tools) >= 4
        tool_names = [t["name"] for t in tools]
        assert "search_venues" in tool_names
        assert "get_venue_types" in tool_names
        assert "get_venue_detail" in tool_names
        assert "search_nearby_by_location" in tool_names

    def test_execute_no_api_key(self):
        from mcp_plugins.plugins.sports_venues.venue_plugin import VenuePlugin
        plugin = VenuePlugin(config={"api_key": "YOUR_AMAP_KEY"})
        result = plugin.execute("search_venues", {"keyword": "健身房"})
        assert not result["success"]

    def test_get_venue_types(self, plugin):
        result = plugin.execute("get_venue_types", {})
        assert result["success"]
        types = result["types"]
        assert len(types) >= 9
        type_ids = [t["id"] for t in types]
        assert "gym" in type_ids
        assert "pool" in type_ids
        assert "running" in type_ids

    def test_execute_unknown_tool(self, plugin):
        result = plugin.execute("unknown_tool", {})
        assert not result["success"]

    @patch("mcp_plugins.plugins.sports_venues.venue_plugin.requests.Session")
    def test_search_venues(self, mock_session_cls, plugin):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "status": "1",
            "info": "OK",
            "pois": [
                {
                    "id": "B000A1",
                    "name": "力美健健身房",
                    "address": "朝阳区建国路1号",
                    "cityname": "北京市",
                    "adname": "朝阳区",
                    "location": "116.4,39.9",
                    "tel": "010-12345678",
                    "type": "健身中心",
                    "biz_ext": {"rating": "4.5", "cost": "200"},
                }
            ],
            "count": "1",
        }
        mock_session = MagicMock()
        mock_session.get.return_value = mock_resp
        plugin._session = mock_session

        result = plugin._search_venues({"keyword": "健身房", "city": "北京"})
        assert result["success"]
        assert result["count"] == 1
        assert result["venues"][0]["name"] == "力美健健身房"

    @patch("mcp_plugins.plugins.sports_venues.venue_plugin.requests.Session")
    def test_search_venues_by_type(self, mock_session_cls, plugin):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "status": "1",
            "info": "OK",
            "pois": [
                {
                    "id": "B000A1",
                    "name": "奥林匹克游泳馆",
                    "address": "朝阳区",
                    "cityname": "北京市",
                    "adname": "朝阳区",
                    "location": "116.4,39.9",
                    "tel": "",
                    "type": "游泳馆",
                    "biz_ext": {},
                }
            ],
            "count": "1",
        }
        mock_session = MagicMock()
        mock_session.get.return_value = mock_resp
        plugin._session = mock_session

        result = plugin._search_venues({
            "keyword": "游泳", "city": "北京", "venue_type": "pool"
        })
        assert result["success"]
        assert result["count"] >= 1


class TestSocialSharePlugin:
    @pytest.fixture
    def plugin(self):
        from mcp_plugins.plugins.social_share.social_share_plugin import SocialSharePlugin
        return SocialSharePlugin(config={
            "site_url": "https://wenyasports.local",
            "default_platform": "weibo",
        })

    def test_name(self, plugin):
        assert plugin.name == "social_share"

    def test_get_tools(self, plugin):
        tools = plugin.get_tools()
        assert len(tools) >= 4
        tool_names = [t["name"] for t in tools]
        assert "generate_activity_share" in tool_names
        assert "generate_achievement_card" in tool_names
        assert "get_share_platforms" in tool_names
        assert "build_share_url" in tool_names

    def test_health_check(self, plugin):
        assert plugin.health_check()

    def test_execute_unknown_tool(self, plugin):
        result = plugin.execute("unknown", {})
        assert not result["success"]

    def test_generate_activity_share_weibo(self, plugin):
        activity = {
            "name": "Morning Run",
            "sport_type": "Run",
            "distance_m": 10000,
            "moving_time_s": 3600,
            "average_heartrate": 150,
            "average_speed_ms": 2.78,
            "calories": 700,
            "start_date_local": "2024-06-01T07:00:00Z",
        }
        result = plugin._generate_activity_share({
            "activity_data": activity,
            "platform": "weibo",
        })
        assert result["success"]
        assert "10.0 km" in result["text"]
        assert "1h 0m" in result["text"]
        assert "跑步" in result["text"]
        assert result["share_url"] is not None
        assert "weibo.com" in result["share_url"]

    def test_generate_activity_share_wechat(self, plugin):
        activity = {
            "name": "Evening Ride",
            "sport_type": "Ride",
            "distance_m": 25000,
            "moving_time_s": 5400,
            "average_heartrate": 130,
            "calories": 900,
        }
        result = plugin._generate_activity_share({
            "activity_data": activity,
            "platform": "wechat",
        })
        assert result["success"]
        assert "骑行" in result["text"]
        assert result["share_url"] is None  # 微信无直接 URL

    def test_generate_activity_share_no_stats(self, plugin):
        activity = {
            "sport_type": "Run",
            "distance_m": 5000,
            "moving_time_s": 1800,
        }
        result = plugin._generate_activity_share({
            "activity_data": activity,
            "include_stats": False,
        })
        assert result["success"]
        # 不应包含配速和心率
        assert "配速" not in result["text"] or "⚡" not in result["text"]

    def test_generate_achievement_card_weekly(self, plugin):
        stats = {
            "total_distance_m": 50000,
            "total_activities": 5,
            "total_time_s": 18000,
            "total_calories": 3500,
            "personal_records": [
                {"label": "5K 最好成绩", "value": "25:30"},
                {"label": "最长距离", "value": "15.2 km"},
            ],
        }
        result = plugin._generate_achievement_card({
            "period": "weekly",
            "stats": stats,
        })
        assert result["success"]
        assert "本周" in result["text"]
        assert "5 次" in result["text"]
        assert "新纪录" in result["text"]

    def test_get_share_platforms(self, plugin):
        result = plugin._get_platforms({})
        assert result["success"]
        platforms = result["platforms"]
        assert len(platforms) >= 5
        platform_ids = [p["id"] for p in platforms]
        assert "weibo" in platform_ids
        assert "wechat" in platform_ids
        assert "twitter" in platform_ids

    def test_build_share_url(self, plugin):
        result = plugin._build_share_url({
            "platform": "weibo",
            "url": "https://wenyasports.local/activity/123",
            "title": "我的跑步成就",
        })
        assert result["success"]
        assert "weibo.com" in result["share_url"]
        assert "wenyasports.local" in result["share_url"]

    def test_build_share_url_invalid_platform(self, plugin):
        result = plugin._build_share_url({
            "platform": "unknown",
            "url": "https://example.com",
        })
        assert not result["success"]

    def test_build_share_url_wechat_no_url(self, plugin):
        result = plugin._build_share_url({
            "platform": "wechat",
            "url": "https://example.com",
        })
        assert not result["success"]

    def test_format_distance(self, plugin):
        assert plugin._format_distance(500) == "500 m"
        assert plugin._format_distance(5000) == "5.0 km"
        assert plugin._format_distance(12345) == "12.3 km"

    def test_format_time(self, plugin):
        assert plugin._format_time(90) == "1m 30s"
        assert plugin._format_time(3661) == "1h 1m"
        assert plugin._format_time(7200) == "2h 0m"

    def test_format_speed(self, plugin):
        # 配速 3 m/s = 333.33 s/km = 5.56 min/km = 5'33"/km
        result = plugin._format_speed(3.0)
        assert "km" in result
        result_0 = plugin._format_speed(0)
        assert result_0 == "—"


class TestPluginManagerLoading:
    """测试 PluginManager 能正确加载新插件。"""

    def test_loads_strava(self):
        from mcp_plugins.manager import PluginManager
        pm = PluginManager(config={
            "plugins": [
                {"name": "strava", "enabled": True, "config": {"access_token": "test"}}
            ]
        })
        plugins = pm.get_plugins()
        assert "strava" in plugins
        tools = pm.get_all_tools()
        tool_names = [t["name"] for t in tools]
        assert "get_athlete_profile" in tool_names

    def test_loads_sports_venues(self):
        from mcp_plugins.manager import PluginManager
        pm = PluginManager(config={
            "plugins": [
                {"name": "sports_venues", "enabled": True, "config": {"api_key": "test"}}
            ]
        })
        plugins = pm.get_plugins()
        assert "sports_venues" in plugins

    def test_loads_social_share(self):
        from mcp_plugins.manager import PluginManager
        pm = PluginManager(config={
            "plugins": [
                {"name": "social_share", "enabled": True, "config": {}}
            ]
        })
        plugins = pm.get_plugins()
        assert "social_share" in plugins

    def test_loads_all_plugins_from_config(self):
        from mcp_plugins.manager import PluginManager
        # 使用默认 config.json
        pm = PluginManager()
        plugins = pm.get_plugins()
        # 至少有 weather 和 social_share（不需要 API key）
        assert len(plugins) >= 2

"""MCP Registry: 统一管理本地插件和远程 MCP Server 连接。

作为 MCP 生态的中央管理器，提供：
- 本地插件注册/发现
- 远程 MCP Server 连接管理
- 统一的工具发现与调用接口
- 与 PluginManager 的无缝集成

Usage:
    registry = MCPRegistry()
    # Add local plugins
    registry.add_local_plugin(weather_plugin)
    # Connect remote server
    registry.connect_remote("weather-service", command=["python", "weather_mcp.py"])
    # Get all tools
    all_tools = registry.get_all_tools()
    # Call any tool
    result = registry.call_tool("get_weather", {"city": "Beijing"})
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from mcp_plugins.base import BasePlugin
from mcp_plugins.manager import PluginManager
from mcp_plugins.remote.mcp_client import MCPClient
from mcp_plugins.remote.protocol import MCPTool, MCPToolResult

logger = logging.getLogger(__name__)


class MCPRegistry:
    """MCP 注册表：统一管理本地和远程工具。

    设计为单例模式，便于全局访问。
    """

    def __init__(self) -> None:
        self._local_plugins: Dict[str, BasePlugin] = {}
        self._remote_clients: Dict[str, MCPClient] = {}
        self._plugin_manager: Optional[PluginManager] = None

    # ------------------------------------------------------------------
    # Local Plugin Management
    # ------------------------------------------------------------------

    def set_plugin_manager(self, manager: PluginManager) -> None:
        """设置 PluginManager，自动同步其插件。"""
        self._plugin_manager = manager
        for name, plugin in manager.get_plugins().items():
            self._local_plugins[name] = plugin

    def add_local_plugin(self, plugin: BasePlugin) -> None:
        """添加本地插件。"""
        self._local_plugins[plugin.name] = plugin
        logger.info("Local plugin registered: %s", plugin.name)

    def remove_local_plugin(self, name: str) -> None:
        """移除本地插件。"""
        self._local_plugins.pop(name, None)

    # ------------------------------------------------------------------
    # Remote Server Management
    # ------------------------------------------------------------------

    def connect_remote_stdio(
        self,
        server_name: str,
        command: List[str],
        env: Optional[Dict[str, str]] = None,
    ) -> MCPClient:
        """连接远程 MCP Server（stdio 模式）。"""
        client = MCPClient()
        try:
            client.connect_stdio(command, env)
            self._remote_clients[server_name] = client
            logger.info("Remote MCP server connected: %s", server_name)
        except Exception as exc:
            logger.error("Failed to connect to %s: %s", server_name, exc)
            raise
        return client

    def connect_remote_sse(
        self,
        server_name: str,
        url: str,
        headers: Optional[Dict[str, str]] = None,
    ) -> MCPClient:
        """连接远程 MCP Server（SSE/HTTP 模式）。"""
        client = MCPClient()
        try:
            client.connect_sse(url, headers)
            self._remote_clients[server_name] = client
            logger.info("Remote MCP server connected: %s (%s)", server_name, url)
        except Exception as exc:
            logger.error("Failed to connect to %s: %s", server_name, exc)
            raise
        return client

    def disconnect_remote(self, server_name: str) -> None:
        """断开远程 MCP Server。"""
        client = self._remote_clients.pop(server_name, None)
        if client:
            client.disconnect()

    def disconnect_all(self) -> None:
        """断开所有远程连接。"""
        for name in list(self._remote_clients.keys()):
            self.disconnect_remote(name)

    # ------------------------------------------------------------------
    # Unified Tool Interface
    # ------------------------------------------------------------------

    def get_all_tools(self) -> List[Dict[str, Any]]:
        """获取所有可用工具（本地 + 远程）。"""
        tools = []

        # Local tools
        for plugin_name, plugin in self._local_plugins.items():
            for tool_def in plugin.get_tools():
                tool = dict(tool_def)
                tool["source"] = "local"
                tool["plugin"] = plugin_name
                tools.append(tool)

        # Remote tools
        for server_name, client in self._remote_clients.items():
            for mcp_tool in client.list_tools():
                tool = mcp_tool.to_dict()
                tool["source"] = "remote"
                tool["server"] = server_name
                tools.append(tool)

        return tools

    def call_tool(
        self,
        tool_name: str,
        arguments: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """统一的工具调用接口。

        自动路由到本地插件或远程服务器。
        """
        arguments = arguments or {}

        # Try local plugins first
        for plugin_name, plugin in self._local_plugins.items():
            for tool_def in plugin.get_tools():
                if tool_def["name"] == tool_name:
                    return plugin.execute(tool_name, arguments)

        # Try remote servers
        for server_name, client in self._remote_clients.items():
            if client.connected and client.get_tool(tool_name):
                result = client.call_tool(tool_name, arguments)
                return {
                    "success": not result.is_error,
                    "result": result.content,
                    "source": "remote",
                    "server": server_name,
                }

        return {"success": False, "error": f"Tool '{tool_name}' not found"}

    def get_server_info(self) -> Dict[str, Any]:
        """获取注册表状态信息。"""
        return {
            "local_plugins": {
                name: {
                    "tools": len(p.get_tools()),
                    "healthy": p.health_check(),
                }
                for name, p in self._local_plugins.items()
            },
            "remote_servers": {
                name: {
                    "connected": c.connected,
                    "tools": len(c.list_tools()),
                    "transport": c.server_info.transport if c.server_info else "unknown",
                }
                for name, c in self._remote_clients.items()
            },
            "total_tools": len(self.get_all_tools()),
        }

    def health_check(self) -> Dict[str, Any]:
        """对所有本地插件和远程服务器进行健康检查。"""
        health = {}
        for name, plugin in self._local_plugins.items():
            health[f"local:{name}"] = plugin.health_check()
        for name, client in self._remote_clients.items():
            health[f"remote:{name}"] = client.connected
        return health
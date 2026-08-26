"""插件化的 MCP (Model Context Protocol) 工具层。

该包提供一套插件化框架：外部工具（天气、地图等）封装为独立插件，
由 PluginManager 动态加载，统一通过 BasePlugin 接口调用，
无需修改核心代码即可扩展新工具。
"""

from mcp_plugins.base import BasePlugin
from mcp_plugins.manager import PluginManager

__all__ = ["BasePlugin", "PluginManager"]
__version__ = "0.1.0"

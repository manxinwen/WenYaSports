"""插件化的 MCP (Model Context Protocol) 工具层。

该包提供一套插件化框架：
- 本地插件系统：PluginManager + BasePlugin
- 远程 MCP 支持：MCPClient、MCPServer、MCPRegistry
- 工具调用管线：缓存、限流、审计等横切关注点
- MCP-Agent Bridge: 将 Agent 能力自动暴露为 MCP 工具

无需修改核心代码即可扩展新工具。
"""

from mcp_plugins.base import BasePlugin
from mcp_plugins.manager import PluginManager
from mcp_plugins.remote import MCPClient, MCPServer, MCPRegistry
from mcp_plugins.bridge import MCPAgentBridge, ToolCard

__all__ = [
    "BasePlugin",
    "PluginManager",
    "MCPClient",
    "MCPServer",
    "MCPRegistry",
    "MCPAgentBridge",
    "ToolCard",
]
__version__ = "2.0.0"

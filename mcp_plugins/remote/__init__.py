"""MCP Remote: 远程 MCP Server/Client 连接支持。

提供：
- MCPClient: 连接远程 MCP Server
- MCPServer: 将本地插件暴露为 MCP 端点
- MCPRegistry: 统一管理本地和远程工具
- Protocol: MCP 协议类型和消息格式
"""

from mcp_plugins.remote.protocol import (
    MCPErrorCode,
    MCPMethod,
    MCPTool,
    MCPToolResult,
    MCPServerInfo,
    JSONRPCRequest,
    JSONRPCResponse,
)
from mcp_plugins.remote.mcp_client import MCPClient
from mcp_plugins.remote.mcp_server import MCPServer
from mcp_plugins.remote.mcp_registry import MCPRegistry

__all__ = [
    "MCPClient",
    "MCPServer",
    "MCPRegistry",
    "MCPTool",
    "MCPToolResult",
    "MCPServerInfo",
    "MCPMethod",
    "MCPErrorCode",
    "JSONRPCRequest",
    "JSONRPCResponse",
]
"""MCP Client: 连接远程 MCP Server，发现和调用工具。

支持多种传输协议：
- stdio: 启动子进程，通过 stdin/stdout 通信
- sse: 通过 HTTP SSE 连接远程服务器
- http: 直接 HTTP POST 请求

Usage:
    client = MCPClient()
    await client.connect_stdio(server_command=["python", "-m", "mcp_server"])
    tools = client.list_tools()
    result = client.call_tool("get_weather", {"city": "Beijing"})
    client.disconnect()
"""

from __future__ import annotations

import json
import logging
import subprocess
import time
from typing import Any, Callable, Dict, List, Optional

from mcp_plugins.remote.protocol import (
    MCPErrorCode,
    MCPMethod,
    MCPTool,
    MCPToolResult,
    MCPServerInfo,
    JSONRPCRequest,
    JSONRPCResponse,
    build_error_response,
    build_success_response,
    parse_jsonrpc_message,
)

logger = logging.getLogger(__name__)


class MCPClient:
    """MCP 客户端：连接远程 MCP Server，管理会话生命周期。

    支持同步和异步两种调用模式（当前实现同步模式，便于集成）。
    """

    def __init__(self) -> None:
        self._server_info: Optional[MCPServerInfo] = None
        self._tools: Dict[str, MCPTool] = {}
        self._process: Optional[subprocess.Popen] = None
        self._request_id: int = 0
        self._connected: bool = False

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def server_info(self) -> Optional[MCPServerInfo]:
        return self._server_info

    # ------------------------------------------------------------------
    # Connection Management
    # ------------------------------------------------------------------

    def connect_stdio(
        self,
        server_command: List[str],
        env: Optional[Dict[str, str]] = None,
        timeout: float = 10.0,
    ) -> MCPServerInfo:
        """通过 stdio 连接 MCP Server。

        Args:
            server_command: 启动服务器的命令和参数
            env: 环境变量
            timeout: 初始化超时时间（秒）
        """
        try:
            self._process = subprocess.Popen(
                server_command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env,
            )
        except Exception as exc:
            raise ConnectionError(f"Failed to start MCP server: {exc}")

        # Send initialize request
        init_request = JSONRPCRequest(
            id=self._next_id(),
            method=MCPMethod.INITIALIZE.value,
            params={
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "clientInfo": {"name": "WenYaSports-Client", "version": "1.0.0"},
            },
        )

        response = self._send_request(init_request, timeout=timeout)
        if response is None or response.error:
            raise ConnectionError(
                f"MCP server initialization failed: {response.error if response else 'No response'}"
            )

        # Parse server info
        result = response.result or {}
        self._server_info = MCPServerInfo(
            name=result.get("serverInfo", {}).get("name", "Unknown"),
            version=result.get("serverInfo", {}).get("version", "0.0.0"),
            capabilities=result.get("capabilities", {}),
            connected=True,
            transport="stdio",
        )

        # Send initialized notification
        self._send_notification(MCPMethod.NOTIFICATION_INITIALIZED.value)

        # Fetch tools
        self._fetch_tools()

        self._connected = True
        logger.info(
            "MCP Server connected: %s v%s (%d tools)",
            self._server_info.name,
            self._server_info.version,
            len(self._tools),
        )
        return self._server_info

    def connect_sse(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        timeout: float = 10.0,
    ) -> MCPServerInfo:
        """通过 SSE 连接远程 MCP Server。

        简化实现：通过 HTTP POST 发送请求，而非真正的 SSE 流。
        """
        import urllib.request

        self._base_url = url.rstrip("/")
        self._headers = headers or {}

        # Initialize
        init_request = JSONRPCRequest(
            id=self._next_id(),
            method=MCPMethod.INITIALIZE.value,
            params={
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "clientInfo": {"name": "WenYaSports-Client", "version": "1.0.0"},
            },
        )

        response = self._send_http_request(init_request, timeout)
        if response is None or response.error:
            raise ConnectionError(
                f"MCP server SSE initialization failed: {response.error if response else 'No response'}"
            )

        result = response.result or {}
        self._server_info = MCPServerInfo(
            name=result.get("serverInfo", {}).get("name", "Remote"),
            version=result.get("serverInfo", {}).get("version", "0.0.0"),
            capabilities=result.get("capabilities", {}),
            connected=True,
            transport="sse",
        )

        self._fetch_tools()
        self._connected = True
        return self._server_info

    def disconnect(self) -> None:
        """断开连接，清理资源。"""
        if self._process and self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
        self._process = None
        self._connected = False
        self._tools.clear()
        self._server_info = None
        logger.info("MCP Client disconnected")

    # ------------------------------------------------------------------
    # Tool Management
    # ------------------------------------------------------------------

    def list_tools(self) -> List[MCPTool]:
        """列出远程服务器提供的所有工具。"""
        return list(self._tools.values())

    def get_tool(self, tool_name: str) -> Optional[MCPTool]:
        """获取指定工具的定义。"""
        return self._tools.get(tool_name)

    def call_tool(
        self,
        tool_name: str,
        arguments: Optional[Dict[str, Any]] = None,
        timeout: float = 30.0,
    ) -> MCPToolResult:
        """调用远程 MCP 工具。

        Args:
            tool_name: 工具名称
            arguments: 工具参数
            timeout: 超时时间

        Returns:
            MCPToolResult
        """
        if not self._connected:
            return MCPToolResult.error_result("Not connected to MCP server")

        request = JSONRPCRequest(
            id=self._next_id(),
            method=MCPMethod.TOOLS_CALL.value,
            params={
                "name": tool_name,
                "arguments": arguments or {},
            },
        )

        response = self._send_request(request, timeout=timeout)
        if response is None:
            return MCPToolResult.error_result("No response from MCP server")

        if response.error:
            return MCPToolResult.error_result(
                response.error.get("message", "Unknown error")
            )

        result = response.result or {}
        content = result.get("content", [])
        is_error = result.get("isError", False)

        return MCPToolResult(content=content, is_error=is_error)

    # ------------------------------------------------------------------
    # Internal Helpers
    # ------------------------------------------------------------------

    def _fetch_tools(self) -> None:
        """从远程服务器获取工具列表。"""
        request = JSONRPCRequest(
            id=self._next_id(),
            method=MCPMethod.TOOLS_LIST.value,
        )

        response = self._send_request(request)
        if response is None or response.error:
            logger.warning("Failed to fetch tools: %s", response.error if response else "No response")
            return

        tools_data = response.result or {}
        for tool_def in tools_data.get("tools", []):
            tool = MCPTool(
                name=tool_def["name"],
                description=tool_def.get("description", ""),
                input_schema=tool_def.get("inputSchema", {}),
                server_name=self._server_info.name if self._server_info else "remote",
            )
            self._tools[tool.name] = tool

    def _send_request(
        self,
        request: JSONRPCRequest,
        timeout: float = 10.0,
    ) -> Optional[JSONRPCResponse]:
        """发送 JSON-RPC 请求并等待响应。"""
        if self._process is None:
            return None

        raw_request = json.dumps(request.to_dict()) + "\n"

        try:
            self._process.stdin.write(raw_request)
            self._process.stdin.flush()
        except (BrokenPipeError, OSError) as exc:
            logger.error("Failed to write to MCP server: %s", exc)
            return None

        try:
            line = self._process.stdout.readline()
            if not line:
                return None
            return parse_jsonrpc_message(line.strip())
        except Exception as exc:
            logger.error("Failed to read from MCP server: %s", exc)
            return None

    def _send_notification(self, method: str) -> None:
        """发送 JSON-RPC 通知（无需响应）。"""
        if self._process is None:
            return
        notification = {"jsonrpc": "2.0", "method": method}
        try:
            self._process.stdin.write(json.dumps(notification) + "\n")
            self._process.stdin.flush()
        except (BrokenPipeError, OSError):
            pass

    def _send_http_request(
        self,
        request: JSONRPCRequest,
        timeout: float = 10.0,
    ) -> Optional[JSONRPCResponse]:
        """通过 HTTP 发送 JSON-RPC 请求。"""
        import urllib.request

        url = f"{self._base_url}/mcp"
        data = json.dumps(request.to_dict()).encode("utf-8")

        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        headers.update(getattr(self, "_headers", {}))

        try:
            req = urllib.request.Request(url, data=data, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read().decode("utf-8")
                return parse_jsonrpc_message(body)
        except Exception as exc:
            logger.error("HTTP request failed: %s", exc)
            return None

    def _next_id(self) -> int:
        self._request_id += 1
        return self._request_id
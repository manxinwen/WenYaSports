"""MCP Server: 将本地插件暴露为 MCP 协议端点。

支持传输方式：
- stdio: 从 stdin 读取 JSON-RPC 请求，写入 stdout
- http: 通过 HTTP POST 接收请求（FastAPI 集成）

Usage (stdio mode):
    server = MCPServer(plugin_manager=manager)
    server.serve_stdio()

Usage (http mode):
    from fastapi import FastAPI
    app = FastAPI()
    server = MCPServer(plugin_manager=manager)
    app.post("/mcp")(server.handle_http_request)
"""

from __future__ import annotations

import json
import logging
import sys
from typing import Any, Callable, Dict, List, Optional

from mcp_plugins.base import BasePlugin
from mcp_plugins.manager import PluginManager
from mcp_plugins.remote.protocol import (
    MCPErrorCode,
    MCPMethod,
    MCPTool,
    MCPToolResult,
    JSONRPCRequest,
    JSONRPCResponse,
    build_error_response,
    build_success_response,
    parse_jsonrpc_message,
)

logger = logging.getLogger(__name__)


class MCPServer:
    """MCP 服务器：将本地插件系统暴露为标准 MCP 接口。

    支持客户端的工具发现、工具调用、资源访问等请求。
    可作为独立进程（stdio）或集成到现有 Web 服务（HTTP）。
    """

    def __init__(
        self,
        plugin_manager: Optional[PluginManager] = None,
        plugins: Optional[List[BasePlugin]] = None,
        server_name: str = "WenYaSports-MCP-Server",
        server_version: str = "1.0.0",
    ) -> None:
        self._plugin_manager = plugin_manager
        self._plugins: Dict[str, BasePlugin] = {}

        # If PluginManager is provided, extract its plugins
        if plugin_manager:
            self._plugins.update(plugin_manager.get_plugins())

        # Add any additional plugins
        if plugins:
            for p in plugins:
                self._plugins[p.name] = p

        self._server_name = server_name
        self._server_version = server_version
        self._initialized = False

    @property
    def server_name(self) -> str:
        return self._server_name

    @property
    def initialized(self) -> bool:
        return self._initialized

    def register_plugin(self, plugin: BasePlugin) -> None:
        """动态注册新插件。"""
        self._plugins[plugin.name] = plugin

    def unregister_plugin(self, plugin_name: str) -> None:
        """动态注销插件。"""
        self._plugins.pop(plugin_name, None)

    def get_all_tools(self) -> List[Dict[str, Any]]:
        """获取所有工具定义（MCP 格式）。"""
        tools = []
        for plugin in self._plugins.values():
            for tool_def in plugin.get_tools():
                tools.append({
                    "name": tool_def["name"],
                    "description": tool_def.get("description", ""),
                    "inputSchema": tool_def.get("parameters", {"type": "object"}),
                })
        return tools

    # ------------------------------------------------------------------
    # Request Handling
    # ------------------------------------------------------------------

    def handle_request(self, request: JSONRPCRequest) -> JSONRPCResponse:
        """处理单个 JSON-RPC 请求。"""
        method = request.method
        params = request.params or {}
        request_id = request.id or 0

        # Handle notifications (no id)
        if request.id is None:
            self._handle_notification(method, params)
            return JSONRPCResponse()  # Empty response for notifications

        # Route to appropriate handler
        handlers = {
            MCPMethod.INITIALIZE.value: self._handle_initialize,
            MCPMethod.PING.value: self._handle_ping,
            MCPMethod.TOOLS_LIST.value: self._handle_tools_list,
            MCPMethod.TOOLS_CALL.value: self._handle_tools_call,
            MCPMethod.RESOURCES_LIST.value: self._handle_resources_list,
            MCPMethod.RESOURCES_READ.value: self._handle_resources_read,
            MCPMethod.PROMPTS_LIST.value: self._handle_prompts_list,
            MCPMethod.PROMPTS_GET.value: self._handle_prompts_get,
        }

        handler = handlers.get(method)
        if handler is None:
            return build_error_response(
                request_id,
                MCPErrorCode.METHOD_NOT_FOUND,
                f"Method not found: {method}",
            )

        try:
            result = handler(params)
            return build_success_response(request_id, result)
        except Exception as exc:
            logger.exception("Error handling %s", method)
            return build_error_response(
                request_id,
                MCPErrorCode.INTERNAL_ERROR,
                str(exc),
            )

    def handle_raw_request(self, raw_json: str) -> Optional[str]:
        """处理原始 JSON 字符串请求，返回 JSON 字符串响应。"""
        message = parse_jsonrpc_message(raw_json)
        if message is None:
            error = build_error_response(
                0, MCPErrorCode.PARSE_ERROR, "Parse error"
            )
            return json.dumps(error.to_dict())

        if isinstance(message, JSONRPCRequest):
            response = self.handle_request(message)
            if response.id is not None:
                return json.dumps(response.to_dict())
            return None  # No response for notifications

        return None

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------

    def _handle_initialize(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle initialize request."""
        self._initialized = True
        protocol_version = params.get("protocolVersion", "2024-11-05")
        logger.info(
            "MCP Server initialized (protocol=%s, client=%s)",
            protocol_version,
            params.get("clientInfo", {}).get("name", "unknown"),
        )
        return {
            "protocolVersion": "2024-11-05",
            "serverInfo": {
                "name": self._server_name,
                "version": self._server_version,
            },
            "capabilities": {
                "tools": {},
                "resources": {},
                "prompts": {},
            },
        }

    def _handle_ping(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle ping request."""
        return {}

    def _handle_tools_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle tools/list request."""
        return {"tools": self.get_all_tools()}

    def _handle_tools_call(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle tools/call request."""
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})

        if not tool_name:
            return self._error_tool_result("Tool name is required")

        # Find the tool across all plugins
        for plugin in self._plugins.values():
            for tool_def in plugin.get_tools():
                if tool_def["name"] == tool_name:
                    result = plugin.execute(tool_name, arguments)
                    return self._to_mcp_tool_result(result)

        return self._error_tool_result(f"Tool not found: {tool_name}")

    def _handle_resources_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle resources/list request."""
        resources = []
        for plugin in self._plugins.values():
            if hasattr(plugin, "get_resources"):
                resources.extend(plugin.get_resources())
        return {"resources": resources}

    def _handle_resources_read(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle resources/read request."""
        uri = params.get("uri", "")
        for plugin in self._plugins.values():
            if hasattr(plugin, "read_resource"):
                result = plugin.read_resource(uri)
                if result:
                    return result
        return {"contents": [], "error": f"Resource not found: {uri}"}

    def _handle_prompts_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle prompts/list request."""
        prompts = []
        for plugin in self._plugins.values():
            if hasattr(plugin, "get_prompts"):
                prompts.extend(plugin.get_prompts())
        return {"prompts": prompts}

    def _handle_prompts_get(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle prompts/get request."""
        name = params.get("name", "")
        arguments = params.get("arguments", {})
        for plugin in self._plugins.values():
            if hasattr(plugin, "get_prompt"):
                result = plugin.get_prompt(name, arguments)
                if result:
                    return result
        return {"error": f"Prompt not found: {name}"}

    def _handle_notification(self, method: str, params: Dict[str, Any]) -> None:
        """Handle JSON-RPC notifications (no response expected)."""
        if method == MCPMethod.NOTIFICATION_INITIALIZED.value:
            logger.info("Client initialized notification received")

    # ------------------------------------------------------------------
    # Transport
    # ------------------------------------------------------------------

    def serve_stdio(self) -> None:
        """启动 stdio 模式的 MCP Server（阻塞式）。"""
        logger.info("MCP Server starting in stdio mode...")
        print("MCP Server ready", file=sys.stderr, flush=True)

        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue

            response_str = self.handle_raw_request(line)
            if response_str:
                print(response_str, flush=True)

    def handle_http_request(self, request_body: Dict[str, Any]) -> Dict[str, Any]:
        """处理 HTTP 模式的请求（集成到 FastAPI）。"""
        raw = json.dumps(request_body)
        response_str = self.handle_raw_request(raw)
        if response_str:
            return json.loads(response_str)
        return {}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _to_mcp_tool_result(result: Dict[str, Any]) -> Dict[str, Any]:
        """将插件执行结果转换为 MCP 工具结果格式。"""
        success = result.get("success", True)
        content = []

        if success:
            # Convert result to text content
            if "result" in result:
                content.append({
                    "type": "text",
                    "text": json.dumps(result["result"], ensure_ascii=False, default=str),
                })
            elif "data" in result:
                content.append({
                    "type": "text",
                    "text": json.dumps(result["data"], ensure_ascii=False, default=str),
                })
            else:
                content.append({
                    "type": "text",
                    "text": json.dumps(result, ensure_ascii=False, default=str),
                })
        else:
            error_msg = result.get("error", "Unknown error")
            content.append({"type": "text", "text": error_msg})

        return {
            "content": content,
            "isError": not success,
        }

    @staticmethod
    def _error_tool_result(message: str) -> Dict[str, Any]:
        return {
            "content": [{"type": "text", "text": message}],
            "isError": True,
        }
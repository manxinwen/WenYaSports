"""Tests for MCP (Model Context Protocol) implementation."""

import json
from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest

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
from mcp_plugins.remote.mcp_client import MCPClient
from mcp_plugins.remote.mcp_server import MCPServer
from mcp_plugins.remote.mcp_registry import MCPRegistry
from mcp_plugins.base import BasePlugin


# ---------------------------------------------------------------------------
# Protocol Tests
# ---------------------------------------------------------------------------

class TestProtocol:
    def test_jsonrpc_request_to_dict(self):
        req = JSONRPCRequest(id=1, method="tools/list", params={"key": "val"})
        d = req.to_dict()
        assert d["jsonrpc"] == "2.0"
        assert d["id"] == 1
        assert d["method"] == "tools/list"
        assert d["params"] == {"key": "val"}

    def test_jsonrpc_response_to_dict(self):
        resp = JSONRPCResponse(id=1, result={"tools": []})
        d = resp.to_dict()
        assert d["jsonrpc"] == "2.0"
        assert d["id"] == 1
        assert d["result"] == {"tools": []}

    def test_jsonrpc_response_error(self):
        resp = JSONRPCResponse(id=1, error={"code": -32600, "message": "Invalid"})
        d = resp.to_dict()
        assert "result" not in d
        assert d["error"]["code"] == -32600

    def test_parse_request(self):
        raw = '{"jsonrpc": "2.0", "id": 1, "method": "tools/list"}'
        msg = parse_jsonrpc_message(raw)
        assert isinstance(msg, JSONRPCRequest)
        assert msg.id == 1
        assert msg.method == "tools/list"

    def test_parse_response(self):
        raw = '{"jsonrpc": "2.0", "id": 1, "result": {"ok": true}}'
        msg = parse_jsonrpc_message(raw)
        assert isinstance(msg, JSONRPCResponse)
        assert msg.result == {"ok": True}

    def test_parse_invalid_json(self):
        raw = "not valid json"
        msg = parse_jsonrpc_message(raw)
        assert msg is None

    def test_build_success(self):
        resp = build_success_response(42, {"status": "ok"})
        assert resp.id == 42
        assert resp.result == {"status": "ok"}
        assert resp.error is None

    def test_build_error(self):
        resp = build_error_response(42, -32600, "Bad Request")
        assert resp.id == 42
        assert resp.error["code"] == -32600
        assert resp.error["message"] == "Bad Request"

    def test_mcp_tool(self):
        tool = MCPTool(
            name="get_weather",
            description="Get weather for a city",
            input_schema={"type": "object", "properties": {"city": {"type": "string"}}},
        )
        d = tool.to_dict()
        assert d["name"] == "get_weather"
        assert "inputSchema" in d

    def test_mcp_tool_result_text(self):
        result = MCPToolResult.text_result("Sunny 25C")
        assert not result.is_error
        assert result.content[0]["text"] == "Sunny 25C"

    def test_mcp_tool_result_error(self):
        result = MCPToolResult.error_result("City not found")
        assert result.is_error
        assert "City not found" in result.content[0]["text"]

    def test_server_info(self):
        info = MCPServerInfo(name="test", capabilities={"tools": {}})
        d = info.to_dict()
        assert d["name"] == "test"
        assert d["connected"] is False


# ---------------------------------------------------------------------------
# MCP Server Tests
# ---------------------------------------------------------------------------

class MockPlugin(BasePlugin):
    """Mock plugin for testing."""

    @property
    def name(self):
        return "test_plugin"

    @property
    def description(self):
        return "A test plugin"

    @property
    def version(self):
        return "1.0.0"

    def __init__(self, config=None):
        self.config = config or {}

    def get_tools(self):
        return [
            {
                "name": "greet",
                "description": "Greet someone",
                "parameters": {
                    "type": "object",
                    "properties": {"name": {"type": "string"}},
                },
            },
            {
                "name": "add",
                "description": "Add two numbers",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "a": {"type": "number"},
                        "b": {"type": "number"},
                    },
                },
            },
        ]

    def execute(self, tool_name, parameters):
        if tool_name == "greet":
            name = parameters.get("name", "World")
            return {"success": True, "result": f"Hello, {name}!"}
        elif tool_name == "add":
            a = parameters.get("a", 0)
            b = parameters.get("b", 0)
            return {"success": True, "result": a + b}
        return {"success": False, "error": f"Unknown tool: {tool_name}"}

    def health_check(self):
        return True


class TestMCPServer:
    @pytest.fixture
    def server(self):
        plugin = MockPlugin()
        return MCPServer(
            plugins=[plugin],
            server_name="Test-Server",
            server_version="2.0.0",
        )

    def test_handle_initialize(self, server):
        req = JSONRPCRequest(id=1, method=MCPMethod.INITIALIZE.value)
        resp = server.handle_request(req)
        assert resp.id == 1
        assert resp.result["serverInfo"]["name"] == "Test-Server"
        assert server.initialized

    def test_handle_tools_list(self, server):
        server._initialized = True
        req = JSONRPCRequest(id=2, method=MCPMethod.TOOLS_LIST.value)
        resp = server.handle_request(req)
        tools = resp.result["tools"]
        assert len(tools) == 2
        tool_names = [t["name"] for t in tools]
        assert "greet" in tool_names
        assert "add" in tool_names

    def test_handle_tools_call_success(self, server):
        server._initialized = True
        req = JSONRPCRequest(
            id=3,
            method=MCPMethod.TOOLS_CALL.value,
            params={"name": "greet", "arguments": {"name": "Alice"}},
        )
        resp = server.handle_request(req)
        assert resp.id == 3
        assert resp.result["isError"] is False
        assert "Hello, Alice!" in resp.result["content"][0]["text"]

    def test_handle_tools_call_not_found(self, server):
        server._initialized = True
        req = JSONRPCRequest(
            id=4,
            method=MCPMethod.TOOLS_CALL.value,
            params={"name": "nonexistent", "arguments": {}},
        )
        resp = server.handle_request(req)
        assert resp.result["isError"] is True

    def test_handle_method_not_found(self, server):
        req = JSONRPCRequest(id=5, method="unknown/method")
        resp = server.handle_request(req)
        assert resp.error is not None
        assert resp.error["code"] == MCPErrorCode.METHOD_NOT_FOUND

    def test_handle_ping(self, server):
        req = JSONRPCRequest(id=6, method=MCPMethod.PING.value)
        resp = server.handle_request(req)
        assert resp.id == 6

    def test_handle_raw_request(self, server):
        raw = json.dumps({"jsonrpc": "2.0", "id": 7, "method": "ping"})
        result = server.handle_raw_request(raw)
        assert result is not None
        parsed = json.loads(result)
        assert parsed["id"] == 7

    def test_handle_invalid_json(self, server):
        result = server.handle_raw_request("invalid")
        assert result is not None
        parsed = json.loads(result)
        assert parsed["error"]["code"] == MCPErrorCode.PARSE_ERROR

    def test_register_plugin(self, server):
        initial_tools = len(server.get_all_tools())

        class ExtraPlugin(MockPlugin):
            @property
            def name(self):
                return "extra_plugin"

        extra = ExtraPlugin()
        server.register_plugin(extra)
        assert len(server.get_all_tools()) > initial_tools

    def test_unregister_plugin(self, server):
        server.unregister_plugin("test_plugin")
        assert len(server.get_all_tools()) == 0

    def test_handle_notification(self, server):
        # Notifications have no id
        req = JSONRPCRequest(
            method=MCPMethod.NOTIFICATION_INITIALIZED.value,
        )
        resp = server.handle_request(req)
        # Should return empty response (no id)
        d = resp.to_dict()
        assert d["id"] is None


# ---------------------------------------------------------------------------
# MCP Registry Tests
# ---------------------------------------------------------------------------

class TestMCPRegistry:
    @pytest.fixture
    def registry(self):
        return MCPRegistry()

    @pytest.fixture
    def registry_with_plugin(self, registry):
        plugin = MockPlugin()
        registry.add_local_plugin(plugin)
        return registry

    def test_add_local_plugin(self, registry_with_plugin):
        tools = registry_with_plugin.get_all_tools()
        assert len(tools) == 2

    def test_call_local_tool(self, registry_with_plugin):
        result = registry_with_plugin.call_tool("greet", {"name": "Bob"})
        assert result["success"] is True
        assert "Hello, Bob!" in result["result"]

    def test_call_unknown_tool(self, registry_with_plugin):
        result = registry_with_plugin.call_tool("nonexistent")
        assert result["success"] is False

    def test_remove_local_plugin(self, registry_with_plugin):
        registry_with_plugin.remove_local_plugin("test_plugin")
        tools = registry_with_plugin.get_all_tools()
        assert len(tools) == 0

    def test_server_info(self, registry_with_plugin):
        info = registry_with_plugin.get_server_info()
        assert "local_plugins" in info
        assert info["total_tools"] == 2

    def test_health_check(self, registry_with_plugin):
        health = registry_with_plugin.health_check()
        assert health["local:test_plugin"] is True

    def test_source_marking(self, registry_with_plugin):
        tools = registry_with_plugin.get_all_tools()
        for tool in tools:
            assert tool["source"] == "local"

    def test_empty_registry(self, registry):
        tools = registry.get_all_tools()
        assert len(tools) == 0
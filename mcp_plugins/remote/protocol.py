"""MCP Protocol: JSON-RPC 2.0 message types and constants.

Implements the core MCP (Model Context Protocol) specification:
- JSON-RPC 2.0 message format
- Tools listing and calling
- Resources and prompts
- Capability negotiation

Reference: https://modelcontextprotocol.io/
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Union


class MCPMethod(str, Enum):
    """MCP JSON-RPC method names."""
    # Lifecycle
    INITIALIZE = "initialize"
    NOTIFICATION_INITIALIZED = "notifications/initialized"
    PING = "ping"

    # Tools
    TOOLS_LIST = "tools/list"
    TOOLS_CALL = "tools/call"

    # Resources
    RESOURCES_LIST = "resources/list"
    RESOURCES_READ = "resources/read"
    RESOURCES_TEMPLATES_LIST = "resources/templates/list"

    # Prompts
    PROMPTS_LIST = "prompts/list"
    PROMPTS_GET = "prompts/get"

    # Sampling (client -> server)
    SAMPLING_CREATE_MESSAGE = "sampling/createMessage"


@dataclass
class JSONRPCRequest:
    """JSON-RPC 2.0 request."""
    jsonrpc: str = "2.0"
    id: Optional[int] = None
    method: str = ""
    params: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {"jsonrpc": self.jsonrpc, "method": self.method}
        if self.id is not None:
            d["id"] = self.id
        if self.params is not None:
            d["params"] = self.params
        return d


@dataclass
class JSONRPCResponse:
    """JSON-RPC 2.0 response."""
    jsonrpc: str = "2.0"
    id: Optional[int] = None
    result: Optional[Any] = None
    error: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {"jsonrpc": self.jsonrpc, "id": self.id}
        if self.error:
            d["error"] = self.error
        else:
            d["result"] = self.result
        return d


@dataclass
class MCPTool:
    """MCP Tool definition."""
    name: str
    description: str = ""
    input_schema: Dict[str, Any] = field(default_factory=dict)
    server_name: str = ""  # Which server provides this tool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema or {"type": "object"},
        }


@dataclass
class MCPToolResult:
    """Result of an MCP tool call."""
    content: List[Dict[str, Any]] = field(default_factory=list)
    is_error: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "content": self.content,
            "isError": self.is_error,
        }

    @classmethod
    def text_result(cls, text: str) -> "MCPToolResult":
        return cls(content=[{"type": "text", "text": text}])

    @classmethod
    def error_result(cls, message: str) -> "MCPToolResult":
        return cls(
            content=[{"type": "text", "text": message}],
            is_error=True,
        )


@dataclass
class MCPServerInfo:
    """Information about a connected MCP server."""
    name: str
    version: str = "1.0.0"
    capabilities: Dict[str, Any] = field(default_factory=dict)
    tools: List[MCPTool] = field(default_factory=list)
    connected: bool = False
    transport: str = "stdio"  # stdio, sse, http

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "capabilities": self.capabilities,
            "tools": [t.to_dict() for t in self.tools],
            "connected": self.connected,
            "transport": self.transport,
        }


def parse_jsonrpc_message(raw: str) -> Union[JSONRPCRequest, JSONRPCResponse, None]:
    """Parse a raw JSON string into a JSON-RPC message."""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None

    if "method" in data:
        return JSONRPCRequest(
            id=data.get("id"),
            method=data["method"],
            params=data.get("params"),
        )
    elif "result" in data or "error" in data:
        return JSONRPCResponse(
            id=data.get("id"),
            result=data.get("result"),
            error=data.get("error"),
        )
    return None


def build_success_response(request_id: int, result: Any) -> JSONRPCResponse:
    return JSONRPCResponse(id=request_id, result=result)


def build_error_response(
    request_id: int, code: int, message: str, data: Optional[Any] = None
) -> JSONRPCResponse:
    error: Dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        error["data"] = data
    return JSONRPCResponse(id=request_id, error=error)


# Standard MCP error codes
class MCPErrorCode:
    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603
    SERVER_NOT_INITIALIZED = -32002
    UNKNOWN_TOOL = -32004
    TOOL_EXECUTION_ERROR = -32005
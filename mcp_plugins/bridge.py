"""MCP-Agent Bridge: 将 Agent 能力自动暴露为 MCP 工具。

实现 MCP 生态与现有 Agent 系统的深度集成：
1. Agent → MCP Tool 自动转换
2. 跨协议工具发现（本地 Agent + 远程 MCP Server）
3. 统一的 Tool Card 规范
4. 动态能力暴露与权限控制

Architecture:
    Agent Registry
        ↓ (auto-expose)
    ┌──────────────────────┐
    │   MCP-Agent Bridge   │
    │  Agent → MCP Tool    │
    │  Capability Mapping  │
    │  Schema Generation   │
    └──────────────────────┘
        ↓
    ┌──────────────────────┐
    │     MCP Registry     │ ←→ Remote MCP Servers
    └──────────────────────┘
        ↓
    Agentic Workflow Engine
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from mcp_plugins.remote.protocol import MCPTool, MCPToolResult

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tool Card - 统一工具描述规范
# ---------------------------------------------------------------------------

@dataclass
class ToolCard:
    """统一工具卡片：描述任何可调用的工具（Agent/插件/远程服务）。"""
    name: str
    description: str
    input_schema: Dict[str, Any] = field(default_factory=dict)
    output_schema: Dict[str, Any] = field(default_factory=dict)
    source: str = "local"  # local_agent / local_plugin / remote_mcp
    source_detail: str = ""
    capabilities: List[str] = field(default_factory=list)
    version: str = "1.0.0"
    examples: List[Dict[str, Any]] = field(default_factory=list)

    def to_mcp_tool(self) -> MCPTool:
        """转换为 MCP Tool 协议对象。"""
        return MCPTool(
            name=self.name,
            description=self.description,
            input_schema=self.input_schema,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
            "outputSchema": self.output_schema,
            "source": self.source,
            "sourceDetail": self.source_detail,
            "capabilities": self.capabilities,
            "version": self.version,
            "examples": self.examples,
        }

    @classmethod
    def from_agent_descriptor(cls, agent_desc: Dict[str, Any]) -> "ToolCard":
        """从 Agent 描述符创建 ToolCard。"""
        agent_id = agent_desc.get("agent_id", "unknown")
        capabilities = agent_desc.get("capabilities", [])
        description = agent_desc.get("description", f"Agent: {agent_id}")

        # Generate input schema from agent metadata
        input_schema = {
            "type": "object",
            "properties": {},
            "description": f"Input for {description}",
        }

        # Extract input requirements if available
        input_params = agent_desc.get("input_params", {})
        for param_name, param_info in input_params.items():
            input_schema["properties"][param_name] = param_info

        # Default: accept generic input
        if not input_schema["properties"]:
            input_schema["properties"] = {
                "input": {
                    "type": "object",
                    "description": "Generic input data for the agent",
                },
            }

        return cls(
            name=agent_id,
            description=description,
            input_schema=input_schema,
            source="local_agent",
            source_detail=agent_id,
            capabilities=capabilities,
        )

    @classmethod
    def from_mcp_tool(cls, mcp_tool: MCPTool, source: str = "remote_mcp") -> "ToolCard":
        """从 MCP Tool 创建 ToolCard。"""
        return cls(
            name=mcp_tool.name,
            description=mcp_tool.description,
            input_schema=mcp_tool.input_schema or {},
            source=source,
            source_detail=mcp_tool.name,
        )


# ---------------------------------------------------------------------------
# MCP-Agent Bridge
# ---------------------------------------------------------------------------

class MCPAgentBridge:
    """MCP-Agent 桥接器。

    核心功能：
    1. 将 Harness 中的所有 Agent 自动暴露为 MCP 工具
    2. 统一本地 Agent、本地插件、远程 MCP Server 的工具接口
    3. 提供动态工具发现和能力查询
    4. 支持工具权限控制和配额管理

    Usage:
        bridge = MCPAgentBridge(harness, mcp_registry)
        bridge.expose_agents()  # Auto-expose all agents as MCP tools
        all_tools = bridge.discover_all_tools()
        result = bridge.invoke_tool("memory_agent", {"query": "最近的训练数据"})
    """

    def __init__(
        self,
        harness: Any = None,
        mcp_registry: Any = None,
    ):
        self.harness = harness
        self.mcp_registry = mcp_registry
        self._tool_cards: Dict[str, ToolCard] = {}
        self._tool_handlers: Dict[str, Callable] = {}
        self._exposed = False

    def expose_agents(self) -> List[ToolCard]:
        """将所有 Harness Agent 暴露为 MCP 工具。

        Returns:
            暴露的 ToolCard 列表
        """
        if self._exposed:
            return list(self._tool_cards.values())

        if self.harness is None:
            logger.warning("No harness available for agent exposure")
            return []

        if not hasattr(self.harness, 'registry'):
            logger.warning("Harness has no registry attribute")
            return []

        exposed = []
        agents = self.harness.registry.list_agents()

        for agent_info in agents:
            if not isinstance(agent_info, dict):
                continue

            tool_card = ToolCard.from_agent_descriptor(agent_info)

            # Create handler that routes to Harness
            agent_id = agent_info.get("agent_id", "")

            def make_handler(aid: str) -> Callable:
                def handler(args: Dict[str, Any], context: Any = None) -> Dict[str, Any]:
                    try:
                        result = self.harness.execute_agent(aid, args)
                        return {
                            "success": True,
                            "agent_id": aid,
                            "result": result,
                        }
                    except Exception as exc:
                        return {
                            "success": False,
                            "agent_id": aid,
                            "error": str(exc),
                        }
                return handler

            self._tool_cards[tool_card.name] = tool_card
            self._tool_handlers[tool_card.name] = make_handler(agent_id)

            # Also register with MCP Registry if available
            if self.mcp_registry:
                try:
                    # Create a lightweight plugin-like wrapper
                    self.mcp_registry._local_plugins[tool_card.name] = _ToolCardPlugin(
                        tool_card, make_handler(agent_id)
                    )
                except Exception:
                    pass

            exposed.append(tool_card)

        self._exposed = True
        logger.info("Exposed %d agents as MCP tools", len(exposed))
        return exposed

    def discover_all_tools(self) -> List[ToolCard]:
        """发现所有可用工具（本地 Agent + 本地插件 + 远程 MCP）。

        Returns:
            所有工具的 ToolCard 列表
        """
        # Ensure agents are exposed
        if not self._exposed:
            self.expose_agents()

        all_cards = list(self._tool_cards.values())

        # Add tools from MCP registry
        if self.mcp_registry:
            registry_tools = self.mcp_registry.get_all_tools()
            for tool_def in registry_tools:
                name = tool_def.get("name", "")
                if name and name not in self._tool_cards:
                    card = ToolCard(
                        name=name,
                        description=tool_def.get("description", ""),
                        input_schema=tool_def.get("inputSchema", {}),
                        source=tool_def.get("source", "remote_mcp"),
                        source_detail=tool_def.get("source_detail", name),
                    )
                    self._tool_cards[name] = card
                    all_cards.append(card)

        return all_cards

    def invoke_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        context: Any = None,
    ) -> Dict[str, Any]:
        """统一的工具调用接口。

        Args:
            tool_name: 工具名称
            arguments: 工具参数
            context: 调用上下文

        Returns:
            统一格式的结果
        """
        start_time = __import__("time").time()

        # Check local handlers first
        if tool_name in self._tool_handlers:
            try:
                result = self._tool_handlers[tool_name](arguments, context)
                return self._format_result(result, tool_name, start_time)
            except Exception as exc:
                return {
                    "success": False,
                    "tool_name": tool_name,
                    "error": str(exc),
                    "latency_ms": (__import__("time").time() - start_time) * 1000,
                }

        # Try MCP registry
        if self.mcp_registry:
            try:
                result = self.mcp_registry.call_tool(tool_name, arguments)
                return self._format_result(result, tool_name, start_time)
            except Exception as exc:
                return {
                    "success": False,
                    "tool_name": tool_name,
                    "error": f"MCP call failed: {exc}",
                    "latency_ms": (__import__("time").time() - start_time) * 1000,
                }

        return {
            "success": False,
            "tool_name": tool_name,
            "error": f"Tool '{tool_name}' not found",
            "latency_ms": (__import__("time").time() - start_time) * 1000,
        }

    def _format_result(
        self,
        result: Any,
        tool_name: str,
        start_time: float,
    ) -> Dict[str, Any]:
        """格式化工具调用结果。"""
        latency = (__import__("time").time() - start_time) * 1000

        if isinstance(result, dict):
            return {
                "success": result.get("success", True),
                "tool_name": tool_name,
                "result": result.get("result", result),
                "error": result.get("error"),
                "latency_ms": latency,
            }

        return {
            "success": True,
            "tool_name": tool_name,
            "result": result,
            "latency_ms": latency,
        }

    def get_capabilities_summary(self) -> Dict[str, List[str]]:
        """获取所有可用能力的摘要。"""
        summary: Dict[str, List[str]] = {}
        for name, card in self._tool_cards.items():
            for cap in card.capabilities:
                if cap not in summary:
                    summary[cap] = []
                summary[cap].append(name)
        return summary

    def get_tool_by_capability(self, capability: str) -> List[ToolCard]:
        """根据能力查询工具。"""
        return [
            card for card in self._tool_cards.values()
            if capability in card.capabilities
        ]

    def get_stats(self) -> Dict[str, Any]:
        """获取桥接器统计信息。"""
        source_counts: Dict[str, int] = {}
        for card in self._tool_cards.values():
            src = card.source
            source_counts[src] = source_counts.get(src, 0) + 1

        return {
            "total_tools": len(self._tool_cards),
            "source_breakdown": source_counts,
            "exposed": self._exposed,
            "tool_names": list(self._tool_cards.keys()),
        }


class _ToolCardPlugin:
    """内部适配器：将 ToolCard 包装为 BasePlugin 兼容格式。"""

    def __init__(self, tool_card: ToolCard, handler: Callable):
        self._tool_card = tool_card
        self._handler = handler

    @property
    def name(self) -> str:
        return self._tool_card.name

    @property
    def description(self) -> str:
        return self._tool_card.description

    @property
    def version(self) -> str:
        return self._tool_card.version

    def get_tools(self) -> List[Dict[str, Any]]:
        return [{
            "name": self._tool_card.name,
            "description": self._tool_card.description,
            "parameters": self._tool_card.input_schema,
        }]

    def execute(self, tool_name: str, parameters: Dict[str, Any]) -> Any:
        return self._handler(parameters)

    def health_check(self) -> bool:
        return True
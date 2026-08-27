"""Tests for Agentic Workflow Engine."""

import json
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import pytest

from app.orchestrator.agentic_workflow import (
    AgenticWorkflowEngine,
    WorkflowState,
    WorkflowStatus,
    ToolCall,
    ThoughtNode,
)


class MockAgentRegistry:
    """Mock Agent Registry that mimics the real AgentRegistry interface."""

    def __init__(self, agents: Dict[str, Dict]):
        self._agents = agents

    def list_agents(self) -> List[Dict[str, Any]]:
        return list(self._agents.values())


class MockHarness:
    """Mock Harness for testing."""

    def __init__(self):
        self._agents = {
            "parser": {
                "agent_id": "parser",
                "description": "Parse data from file",
                "capabilities": ["data_parsing", "file_reading"],
                "parameters": {"file_path": {"type": "string"}},
            },
            "memory": {
                "agent_id": "memory",
                "description": "Store and retrieve data",
                "capabilities": ["data_storage", "retrieval"],
                "parameters": {"data": {"type": "object"}},
            },
            "feature_extractor": {
                "agent_id": "feature_extractor",
                "description": "Extract features from data",
                "capabilities": ["feature_extraction", "analysis"],
                "parameters": {"data": {"type": "object"}},
            },
        }
        self.registry = MockAgentRegistry(self._agents)
        self._exec_count = 0

    def execute_agent(self, agent_id: str, input_data: Any) -> Dict[str, Any]:
        self._exec_count += 1
        if agent_id in self._agents:
            return {
                "success": True,
                "agent_id": agent_id,
                "result": f"Result from {agent_id}",
                "data": input_data,
            }
        return {"success": False, "error": f"Unknown agent: {agent_id}"}


class MockMCPRegistry:
    """Mock MCP Registry for testing."""

    def __init__(self):
        self._tools = [
            {
                "name": "get_weather",
                "description": "Get weather for a city",
                "source": "remote_mcp",
            },
            {
                "name": "map_route",
                "description": "Get route between two points",
                "source": "local_plugin",
            },
        ]

    def get_all_tools(self):
        return self._tools

    def call_tool(self, name: str, args: Dict) -> Dict:
        return {"success": True, "tool": name, "result": f"Result from {name}"}


class TestAgenticWorkflowEngine:
    @pytest.fixture
    def engine(self):
        harness = MockHarness()
        mcp = MockMCPRegistry()
        return AgenticWorkflowEngine(
            harness=harness,
            mcp_registry=mcp,
            llm_client=None,  # No LLM for heuristic testing
            max_iterations=3,
            thought_branching=3,
        )

    def test_engine_initialization(self, engine):
        stats = engine.get_stats()
        assert stats["total_tools"] > 0
        assert stats["max_iterations"] == 3
        assert stats["thought_branching"] == 3

    def test_register_tool(self, engine):
        def my_handler(args, inp):
            return {"result": "ok"}

        engine.register_tool("my_tool", my_handler, "My custom tool")
        assert "my_tool" in engine._tools

    def test_run_with_heuristic(self, engine):
        state = engine.run(goal="Analyze training data")
        assert state.status == WorkflowStatus.COMPLETED
        assert state.iteration > 0
        assert len(state.tool_calls) > 0

    def test_workflow_state_to_dict(self, engine):
        state = engine.run(goal="Test goal")
        d = state.to_dict()
        assert "goal" in d
        assert "status" in d
        assert "iteration" in d

    def test_tool_call_structure(self, engine):
        state = engine.run(goal="Test tool calls")
        for tc in state.tool_calls:
            assert isinstance(tc, ToolCall)
            assert tc.tool_name
            assert isinstance(tc.success, bool)

    def test_discover_tools(self, engine):
        tools = engine._discover_tools()
        assert len(tools) > 0
        # Should include harness agents
        assert "parser" in tools
        assert "memory" in tools

    def test_discover_tools_with_override(self, engine):
        tools = engine._discover_tools(override=["parser"])
        assert len(tools) == 1
        assert "parser" in tools

    def test_format_tools_for_llm(self, engine):
        tools = {"parser": {"description": "Parse data", "source": "harness"}}
        formatted = engine._format_tools_for_llm(tools)
        assert "parser" in formatted
        assert "Parse data" in formatted

    def test_heuristic_thinking(self, engine):
        thoughts = engine._heuristic_thinking("test goal", "tools desc", 3)
        assert len(thoughts) <= 3
        assert len(thoughts) > 0
        for t in thoughts:
            assert "reasoning" in t
            assert "tool_calls" in t

    def test_build_observation(self, engine):
        results = [
            ToolCall(tool_name="t1", arguments={}, success=True, result="ok"),
            ToolCall(tool_name="t2", arguments={}, success=False, error="fail"),
        ]
        obs = engine._build_observation(results)
        assert "t1" in obs
        assert "t2" in obs
        assert "✓" in obs  # Success marker
        assert "✗" in obs  # Failure marker

    def test_reflect_heuristic(self, engine):
        results = [
            ToolCall(tool_name="t1", arguments={}, success=True),
            ToolCall(tool_name="t2", arguments={}, success=True),
        ]
        state = WorkflowState(goal="test")
        reflection = engine._reflect("test", results, state)
        assert "quality_score" in reflection
        assert "assessment" in reflection

    def test_critique_heuristic(self, engine):
        result = {"data": "test output"}
        critique = engine._critique(result, "test goal")
        assert "verdict" in critique
        assert "scores" in critique
        assert "overall_score" in critique

    def test_run_with_tool_override(self, engine):
        state = engine.run(goal="Test", tools_override=["parser"])
        assert state.status == WorkflowStatus.COMPLETED

    def test_quality_threshold_gate(self, engine):
        # Set high threshold so heuristic critique fails
        engine.quality_threshold = 99.0
        state = engine.run(goal="Test with high threshold")
        # May fail or iterate due to high threshold
        assert state.iteration > 0


class TestWorkflowState:
    def test_state_creation(self):
        state = WorkflowState(goal="test goal")
        assert state.goal == "test goal"
        assert state.status == WorkflowStatus.PENDING
        assert state.iteration == 0

    def test_state_to_dict(self):
        state = WorkflowState(goal="test", max_iterations=5)
        state.status = WorkflowStatus.COMPLETED
        state.final_result = "Done"
        d = state.to_dict()
        assert d["status"] == "completed"
        assert d["final_result"] == "Done"

    def test_tool_call_creation(self):
        tc = ToolCall(
            tool_name="test_tool",
            arguments={"param": "value"},
            success=True,
            result="output",
            latency_ms=100.0,
        )
        assert tc.tool_name == "test_tool"
        assert tc.success is True
        assert tc.latency_ms == 100.0


class TestThoughtNode:
    def test_node_creation(self):
        node = ThoughtNode(
            id=1,
            content="Test thought",
            score=0.8,
        )
        assert node.id == 1
        assert node.content == "Test thought"
        assert node.score == 0.8
        assert node.is_terminal is False
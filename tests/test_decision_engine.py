"""Tests for LLM Decision Engine and MCP Agent Bridge."""

import json
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import pytest

from app.orchestrator.decision_engine import (
    LLMDecisionEngine,
    DecisionResult,
    CritiqueResult,
    DebateResult,
    DecisionLayer,
    DecisionType,
)
from mcp_plugins.bridge import (
    MCPAgentBridge,
    ToolCard,
)
from mcp_plugins.remote.protocol import MCPTool


# ---------------------------------------------------------------------------
# Decision Engine Tests
# ---------------------------------------------------------------------------

class TestLLMDecisionEngine:
    @pytest.fixture
    def engine(self):
        return LLMDecisionEngine(
            llm_client=None,  # No LLM, use heuristics
            quality_threshold=70.0,
        )

    @pytest.fixture
    def mock_llm_engine(self):
        """Engine with mocked LLM responses."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(
                message=MagicMock(
                    content=json.dumps({
                        "analysis": "目标分析",
                        "recommended_strategy": {
                            "strategy_id": "strategy_a",
                            "reasoning": "最优选择",
                            "expected_benefits": "高效率",
                            "risks": ["风险1"],
                        },
                        "alternatives": [
                            {"strategy_id": "strategy_b", "pros": "", "cons": ""}
                        ],
                        "confidence": 0.85,
                        "fallback_strategy": "fallback",
                    })
                )
            )
        ]
        mock_client.chat.completions.create.return_value = mock_response

        return LLMDecisionEngine(
            llm_client=mock_client,
            quality_threshold=70.0,
        )

    # --- Strategic Decision Tests ---

    def test_strategic_decide_heuristic(self, engine):
        options = [
            {"id": "a", "description": "Analyze data quickly"},
            {"id": "b", "description": "Deep analysis with ML"},
        ]
        result = engine.strategic_decide("analyze training data", options)
        assert isinstance(result, DecisionResult)
        assert result.layer == DecisionLayer.STRATEGIC
        assert result.chosen_option

    def test_strategic_decide_with_llm(self, mock_llm_engine):
        options = [{"id": "a", "description": "Option A"}]
        result = mock_llm_engine.strategic_decide("test goal", options)
        assert result.chosen_option.get("strategy_id") == "strategy_a"
        assert result.confidence == 0.85

    def test_strategic_decide_empty_options(self, engine):
        result = engine.strategic_decide("test", [])
        assert result.chosen_option == {}
        assert result.confidence == 0.0

    def test_strategic_decide_with_constraints(self, engine):
        options = [{"id": "a", "description": "Fast option"}]
        result = engine.strategic_decide(
            "test", options, constraints=["must be fast"]
        )
        assert result.layer == DecisionLayer.STRATEGIC

    # --- Tactical Decision Tests ---

    def test_tactical_decide_heuristic(self, engine):
        tools = [
            {"name": "parser", "description": "Parse data"},
            {"name": "memory", "description": "Store data"},
        ]
        result = engine.tactical_decide("parse and store", tools)
        assert isinstance(result, DecisionResult)
        assert result.layer == DecisionLayer.TACTICAL
        assert "tool_chain" in result.chosen_option

    def test_tactical_decide_with_llm(self, mock_llm_engine):
        # Override mock for tactical decision
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(
                message=MagicMock(
                    content=json.dumps({
                        "tool_chain": [
                            {"tool": "parser", "arguments": {}, "order": 1}
                        ],
                        "parameter_optimizations": [],
                        "recovery_plan": "retry",
                        "confidence": 0.9,
                    })
                )
            )
        ]
        mock_client.chat.completions.create.return_value = mock_response

        eng = LLMDecisionEngine(llm_client=mock_client)
        tools = [{"name": "parser", "description": "Parse"}]
        result = eng.tactical_decide("test", tools)
        assert len(result.chosen_option["tool_chain"]) == 1

    def test_tactical_decide_empty_tools(self, engine):
        result = engine.tactical_decide("test", [])
        assert result.chosen_option["tool_chain"] == []

    # --- Critique Tests ---

    def test_critique_heuristic_pass(self, engine):
        artifact = "This is a good result with enough detail to be useful for the user." * 10
        result = engine.critique(artifact, "test goal")
        assert isinstance(result, CritiqueResult)
        assert "overall_score" in result.scores or result.overall_score > 0

    def test_critique_heuristic_fail_empty(self, engine):
        result = engine.critique("", "test")
        assert result.verdict == "fail"
        assert result.pass_gate is False

    def test_critique_heuristic_fail_short(self, engine):
        result = engine.critique("Too short", "test")
        assert result.pass_gate is False

    def test_critique_with_llm(self, mock_llm_engine):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(
                message=MagicMock(
                    content=json.dumps({
                        "verdict": "pass",
                        "scores": {
                            "accuracy": 90, "completeness": 85,
                            "depth": 80, "actionability": 88,
                            "conciseness": 92,
                        },
                        "overall_score": 87,
                        "strengths": ["Accurate", "Complete"],
                        "issues": [],
                        "suggestions": [],
                        "pass_gate": True,
                        "confidence": 0.9,
                    })
                )
            )
        ]
        mock_client.chat.completions.create.return_value = mock_response

        eng = LLMDecisionEngine(llm_client=mock_client)
        result = eng.critique("test artifact", "test goal")
        assert result.verdict == "pass"
        assert result.overall_score == 87
        assert result.pass_gate is True

    def test_critique_history(self, engine):
        engine.critique("A good result " * 20, "goal 1")
        engine.critique("", "goal 2")
        assert len(engine._critique_history) == 2

    # --- Debate Tests ---

    def test_debate_insufficient_viewpoints(self, engine):
        result = engine.debate("test topic", [{"view": "A"}])
        assert isinstance(result, DebateResult)
        assert result.agreement_level == 0.5

    def test_debate_with_llm(self, mock_llm_engine):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(
                message=MagicMock(
                    content=json.dumps({
                        "comparative_analysis": "A is better",
                        "winning_position": "A",
                        "synthesis": "Combined approach",
                        "confidence": 0.85,
                        "final_verdict": "Use A",
                        "remaining_uncertainties": ["cost"],
                    })
                )
            )
        ]
        mock_client.chat.completions.create.return_value = mock_response

        eng = LLMDecisionEngine(llm_client=mock_client)
        viewpoints = [
            {"position": "A", "argument": "Fast"},
            {"position": "B", "argument": "Accurate"},
        ]
        result = eng.debate("test topic", viewpoints)
        assert result.final_verdict == "Use A"
        assert result.agreement_level == 0.85

    def test_debate_history(self, engine):
        engine.debate("topic 1", [{}, {}])
        assert len(engine._debate_history) == 1

    # --- Error Recovery Tests ---

    def test_error_recovery_heuristic_retryable(self, engine):
        result = engine.error_recovery("Connection timeout", {})
        assert result.chosen_option["should_retry"] is True
        assert result.chosen_option["should_escalate"] is False

    def test_error_recovery_heuristic_non_retryable(self, engine):
        result = engine.error_recovery("Invalid input", {})
        assert result.chosen_option["should_retry"] is False
        assert result.chosen_option["should_escalate"] is True

    def test_error_recovery_attempts_limit(self, engine):
        result = engine.error_recovery("Timeout", {}, attempts=5)
        assert result.chosen_option["should_escalate"] is True

    def test_error_recovery_with_llm(self, mock_llm_engine):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(
                message=MagicMock(
                    content=json.dumps({
                        "error_analysis": "Network issue",
                        "recovery_options": [
                            {
                                "strategy": "Retry with backoff",
                                "probability_of_success": 0.8,
                                "cost": "low",
                                "steps": ["Wait 5s", "Retry"],
                            }
                        ],
                        "recommended_strategy": "Retry with backoff",
                        "should_retry": True,
                        "should_escalate": False,
                    })
                )
            )
        ]
        mock_client.chat.completions.create.return_value = mock_response

        eng = LLMDecisionEngine(llm_client=mock_client)
        result = eng.error_recovery("Timeout", {})
        assert result.chosen_option["should_retry"] is True

    # --- Stats Test ---

    def test_get_stats(self, engine):
        stats = engine.get_stats()
        assert "model" in stats
        assert "quality_threshold" in stats
        assert stats["total_decisions"] == 0

    def test_get_stats_after_critiques(self, engine):
        engine.critique("Good " * 20, "goal")
        stats = engine.get_stats()
        assert stats["total_critiques"] == 1


# ---------------------------------------------------------------------------
# MCP Agent Bridge Tests
# ---------------------------------------------------------------------------

class MockAgentRegistryForBridge:
    """Mock Agent Registry for bridge testing."""
    def __init__(self, agents):
        self._agents = agents

    def list_agents(self):
        return list(self._agents.values())


class MockHarnessForBridge:
    """Mock Harness for bridge testing."""

    def __init__(self):
        self._agents = {
            "parser": {
                "agent_id": "parser",
                "description": "Parse data from files",
                "capabilities": ["parsing", "file_reading"],
            },
            "memory_agent": {
                "agent_id": "memory_agent",
                "description": "Store and retrieve information",
                "capabilities": ["storage", "retrieval"],
            },
            "feature_extractor": {
                "agent_id": "feature_extractor",
                "description": "Extract features from raw data",
                "capabilities": ["feature_extraction", "analysis"],
            },
        }
        self.registry = MockAgentRegistryForBridge(self._agents)

    def execute_agent(self, agent_id: str, input_data: Any) -> Dict[str, Any]:
        return {"success": True, "agent_id": agent_id, "result": f"OK from {agent_id}"}


class TestToolCard:
    def test_tool_card_creation(self):
        card = ToolCard(
            name="test_tool",
            description="A test tool",
            input_schema={"type": "object", "properties": {"x": {"type": "number"}}},
            source="local_agent",
            capabilities=["test"],
        )
        assert card.name == "test_tool"
        assert card.source == "local_agent"

    def test_tool_card_to_dict(self):
        card = ToolCard(name="test", description="desc")
        d = card.to_dict()
        assert d["name"] == "test"
        assert d["description"] == "desc"
        assert d["source"] == "local"

    def test_tool_card_from_agent_descriptor(self):
        desc = {
            "agent_id": "my_agent",
            "description": "My custom agent",
            "capabilities": ["cap1", "cap2"],
        }
        card = ToolCard.from_agent_descriptor(desc)
        assert card.name == "my_agent"
        assert card.description == "My custom agent"
        assert "cap1" in card.capabilities

    def test_tool_card_from_mcp_tool(self):
        mcp_tool = MCPTool(
            name="remote_tool",
            description="A remote tool",
            input_schema={"type": "object"},
        )
        card = ToolCard.from_mcp_tool(mcp_tool, source="remote_mcp")
        assert card.name == "remote_tool"
        assert card.source == "remote_mcp"

    def test_tool_card_to_mcp_tool(self):
        card = ToolCard(
            name="test",
            description="test",
            input_schema={"type": "object", "properties": {"a": {"type": "string"}}},
        )
        mcp = card.to_mcp_tool()
        assert isinstance(mcp, MCPTool)
        assert mcp.name == "test"


class TestMCPAgentBridge:
    @pytest.fixture
    def bridge(self):
        harness = MockHarnessForBridge()
        return MCPAgentBridge(harness=harness)

    def test_bridge_expose_agents(self, bridge):
        cards = bridge.expose_agents()
        assert len(cards) == 3
        card_names = {c.name for c in cards}
        assert "parser" in card_names
        assert "memory_agent" in card_names

    def test_bridge_expose_agents_idempotent(self, bridge):
        cards1 = bridge.expose_agents()
        cards2 = bridge.expose_agents()
        assert len(cards1) == len(cards2)

    def test_bridge_discover_all_tools(self, bridge):
        bridge.expose_agents()
        tools = bridge.discover_all_tools()
        assert len(tools) >= 3

    def test_bridge_invoke_tool_success(self, bridge):
        bridge.expose_agents()
        result = bridge.invoke_tool("parser", {"file_path": "test.csv"})
        assert result["success"] is True
        assert result["tool_name"] == "parser"

    def test_bridge_invoke_tool_not_found(self, bridge):
        bridge.expose_agents()
        result = bridge.invoke_tool("nonexistent", {})
        assert result["success"] is False

    def test_bridge_get_capabilities_summary(self, bridge):
        bridge.expose_agents()
        summary = bridge.get_capabilities_summary()
        assert "parsing" in summary
        assert "storage" in summary

    def test_bridge_get_tool_by_capability(self, bridge):
        bridge.expose_agents()
        tools = bridge.get_tool_by_capability("parsing")
        assert len(tools) >= 1
        assert tools[0].name == "parser"

    def test_bridge_get_stats(self, bridge):
        bridge.expose_agents()
        stats = bridge.get_stats()
        assert stats["total_tools"] == 3
        assert stats["exposed"] is True

    def test_bridge_no_harness(self):
        bridge = MCPAgentBridge(harness=None)
        cards = bridge.expose_agents()
        assert len(cards) == 0
        stats = bridge.get_stats()
        assert stats["total_tools"] == 0

    def test_bridge_with_mcp_registry(self, bridge):
        """Test integration with MCP Registry (no remote connection needed)."""
        bridge.expose_agents()
        tools = bridge.discover_all_tools()
        assert len(tools) >= 3


class TestDecisionResult:
    def test_decision_result_creation(self):
        result = DecisionResult(
            chosen_option={"key": "value"},
            reasoning="Test reasoning",
            confidence=0.8,
            alternatives_considered=3,
            layer=DecisionLayer.STRATEGIC,
        )
        assert result.chosen_option == {"key": "value"}
        assert result.layer == DecisionLayer.STRATEGIC
        assert result.confidence == 0.8


class TestCritiqueResult:
    def test_critique_result_creation(self):
        result = CritiqueResult(
            verdict="pass",
            scores={"accuracy": 90, "completeness": 85},
            overall_score=87.5,
            issues=[],
            suggestions=[],
            pass_gate=True,
        )
        assert result.verdict == "pass"
        assert result.pass_gate is True
        assert result.overall_score == 87.5


class TestDebateResult:
    def test_debate_result_creation(self):
        result = DebateResult(
            topic="test topic",
            positions=[{"view": "A"}, {"view": "B"}],
            consensus={"synthesis": "C"},
            agreement_level=0.7,
            final_verdict="Use C",
        )
        assert result.topic == "test topic"
        assert len(result.positions) == 2
        assert result.agreement_level == 0.7


class TestDecisionEnums:
    def test_decision_layer_values(self):
        assert DecisionLayer.STRATEGIC.value == "strategic"
        assert DecisionLayer.TACTICAL.value == "tactical"
        assert DecisionLayer.VALIDATION.value == "validation"

    def test_decision_type_values(self):
        assert DecisionType.GOAL_ANALYSIS.value == "goal_analysis"
        assert DecisionType.TOOL_CHOICE.value == "tool_choice"
        assert DecisionType.QUALITY_ASSESSMENT.value == "quality_assessment"
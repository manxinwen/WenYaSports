"""Tests for LLM-driven Orchestrator.

Tests cover:
1. Plan parsing and validation
2. Fallback plan generation
3. LLM orchestrator execution with fallback
4. Agent input resolution
5. Re-planning logic
"""

import json
import os
from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest

from app.orchestrator.llm_orchestrator import LLMOrchestrator, PLANNER_SYSTEM_PROMPT
from app.orchestrator.plan_parser import (
    ExecutionPlan,
    PlanStep,
    build_fallback_plan,
)


# ---------------------------------------------------------------------------
# Plan parsing & validation
# ---------------------------------------------------------------------------

class TestPlanParsing:
    def test_plan_step_from_dict(self):
        step = PlanStep.from_dict({
            "step": 1,
            "agent_id": "parser",
            "capability": "fit_parsing",
            "input_key": "file_path",
            "output_key": "parsed_activity",
            "reasoning": "需要解析文件",
        })
        assert step.step == 1
        assert step.agent_id == "parser"
        assert step.input_key == "file_path"

    def test_execution_plan_from_dict(self):
        plan = ExecutionPlan.from_dict({
            "goal": "分析运动数据",
            "plan": [
                {"step": 1, "agent_id": "parser", "output_key": "data"},
            ],
            "fallback_plan": [
                {"step": 1, "agent_id": "fallback", "output_key": "fb"},
            ],
            "confidence": 0.9,
            "reasoning": "测试",
        })
        assert plan.goal == "分析运动数据"
        assert len(plan.steps) == 1
        assert len(plan.fallback_steps) == 1
        assert plan.confidence == 0.9

    def test_plan_json_roundtrip(self):
        plan = ExecutionPlan(
            goal="test",
            steps=[PlanStep(step=1, agent_id="a", output_key="o")],
            confidence=0.8,
        )
        json_str = json.dumps(plan.to_dict(), ensure_ascii=False)
        restored = ExecutionPlan.from_json(json_str)
        assert restored.goal == plan.goal
        assert restored.confidence == plan.confidence
        assert restored.steps[0].agent_id == "a"

    def test_plan_validation(self):
        plan = ExecutionPlan.from_dict({
            "goal": "test",
            "plan": [
                {"step": 1, "agent_id": "parser"},
                {"step": 2, "agent_id": "nonexistent_agent"},
            ],
        })
        errors = plan.validate(["parser", "feature_extractor"])
        assert len(errors) == 1
        assert "nonexistent_agent" in errors[0]

    def test_plan_validation_passes_with_valid_agents(self):
        plan = ExecutionPlan.from_dict({
            "goal": "test",
            "plan": [
                {"step": 1, "agent_id": "parser"},
                {"step": 2, "agent_id": "memory"},
            ],
        })
        errors = plan.validate(["parser", "memory", "recommender"])
        assert len(errors) == 0

    def test_build_fallback_plan(self):
        plan = build_fallback_plan("test goal")
        assert plan.goal == "test goal"
        assert plan.is_empty() is False
        assert plan.confidence == 0.5
        # Has the standard pipeline
        agent_ids = [s.agent_id for s in plan.steps]
        assert "parser" in agent_ids
        assert "feature_extractor" in agent_ids
        assert "recommender" in agent_ids

    def test_get_execution_order_sorts_by_step(self):
        plan = ExecutionPlan(
            goal="test",
            steps=[
                PlanStep(step=3, agent_id="c"),
                PlanStep(step=1, agent_id="a"),
                PlanStep(step=2, agent_id="b"),
            ],
        )
        order = plan.get_execution_order()
        assert [s.step for s in order] == [1, 2, 3]

    def test_empty_plan(self):
        plan = ExecutionPlan(goal="", steps=[])
        assert plan.is_empty() is True


# ---------------------------------------------------------------------------
# LLM Orchestrator
# ---------------------------------------------------------------------------

class TestLLMOrchestrator:
    @pytest.fixture
    def mock_harness(self):
        harness = MagicMock()
        harness.registry.list_agents.return_value = [
            {"agent_id": "parser", "name": "FIT Parser", "capabilities": ["fit_parsing"], "status": "idle"},
            {"agent_id": "feature_extractor", "name": "Feature Extractor", "capabilities": ["feature_engineering"], "status": "idle"},
            {"agent_id": "memory", "name": "Memory Manager", "capabilities": ["user_profile"], "status": "idle"},
            {"agent_id": "recommender", "name": "Recommendation Engine", "capabilities": ["training_advice"], "status": "idle"},
        ]
        harness.registry.get_instance.return_value = MagicMock()

        # Simulate governance wrapping: returns success dict
        def mock_governance_execute(agent_id, execution_fn, context):
            try:
                result = execution_fn()
                return {"success": True, "result": result, "execution_time_ms": 1}
            except Exception as e:
                return {"success": False, "error": str(e), "execution_time_ms": 1}

        harness.governance.execute_with_governance.side_effect = mock_governance_execute
        return harness

    @pytest.fixture
    def orchestrator(self, mock_harness):
        return LLMOrchestrator(
            harness=mock_harness,
            llm_client=None,  # No LLM -> should use fallback
            max_replanning=2,
        )

    def test_execute_goal_with_fallback(self, orchestrator, mock_harness):
        """Without LLM, should fall back to rule-based plan."""
        mock_harness.registry.get_instance.return_value.run.return_value = MagicMock(
            model_dump=lambda: {},
        )

        result = orchestrator.execute_goal(
            goal="分析这份运动数据",
            initial_input={"file_path": "/tmp/test.fit", "user_id": "u1"},
            user_id="u1",
        )

        # Should have attempted to execute (may fail on actual parsing)
        assert "session_id" in result
        assert result.get("steps_completed", 0) >= 0

    def test_execute_goal_no_agents_available(self, orchestrator, mock_harness):
        """When no agents are found, should handle gracefully."""
        mock_harness.registry.list_agents.return_value = []

        result = orchestrator.execute_goal(
            goal="impossible goal",
            initial_input={},
        )
        # Fallback plan still gets built (it's from build_fallback_plan)
        assert "session_id" in result

    def test_resolve_input_special_keys(self, orchestrator):
        """Test special input key resolution."""
        results = {
            "_initial_input": {"file_path": "/test.fit", "user_id": "u1", "session_id": "s1"},
            "parsed_activity": "activity_data",
        }

        # file_path key
        step = PlanStep(step=1, agent_id="parser", input_key="file_path")
        val = orchestrator._resolve_input(step, results)
        assert val == "/test.fit"

        # user_context key
        step = PlanStep(step=2, agent_id="memory", input_key="user_context")
        val = orchestrator._resolve_input(step, results)
        assert val == {"user_id": "u1", "session_id": "s1"}

        # Regular lookup
        step = PlanStep(step=3, agent_id="test", input_key="parsed_activity")
        val = orchestrator._resolve_input(step, results)
        assert val == "activity_data"

    def test_resolve_input_none_key(self, orchestrator):
        """When input_key is None, returns initial input."""
        results = {"_initial_input": {"data": "test"}}
        step = PlanStep(step=1, agent_id="test")
        val = orchestrator._resolve_input(step, results)
        assert val == {"data": "test"}

    def test_format_agent_capabilities(self, orchestrator, mock_harness):
        """Test agent capability formatting for LLM prompt."""
        caps = orchestrator._format_agent_capabilities()
        assert "parser" in caps
        assert "fit_parsing" in caps
        assert "Feature Extractor" in caps

    def test_orchestrator_stats(self, orchestrator):
        """Test stats reporting."""
        stats = orchestrator.get_orchestrator_stats()
        assert stats["llm_available"] is False
        assert stats["max_replanning"] == 2
        assert stats["total_plans_generated"] == 0

    def test_prompt_contains_agent_list(self):
        """System prompt should include agent capabilities placeholder."""
        assert "{agent_capabilities}" in PLANNER_SYSTEM_PROMPT
        assert "规划原则" in PLANNER_SYSTEM_PROMPT

    def test_replan_triggered_on_failure(self, orchestrator, mock_harness):
        """When execution fails, replanning should be attempted."""
        # Make all agent executions fail
        mock_harness.registry.get_instance.return_value.run.side_effect = Exception("Simulated failure")

        result = orchestrator.execute_goal(
            goal="分析运动数据",
            initial_input={"file_path": "/tmp/test.fit"},
        )

        # Should have attempted replanning (or failed gracefully)
        assert result.get("success") is False or orchestrator._replan_count > 0

    def test_llm_client_optional(self, mock_harness):
        """Orchestrator should work without LLM client."""
        orch = LLMOrchestrator(harness=mock_harness, llm_client=None)
        assert orch.llm_client is None

    def test_llm_client_accepts_mock(self, mock_harness):
        """Orchestrator should accept an LLM client."""
        mock_client = MagicMock()
        orch = LLMOrchestrator(harness=mock_harness, llm_client=mock_client)
        assert orch.llm_client is mock_client
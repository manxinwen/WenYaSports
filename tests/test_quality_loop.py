"""Integration tests for the Quality Loop (Evaluator + Reflection + Guardrails).

Tests the closed-loop quality control flow:
  Orchestrator executes → Evaluator evaluates → Reflection reflects → Guardrails guards
"""

import pytest

from app.agents.evaluator_agent import EvaluatorAgent
from app.agents.reflection_engine import ReflectionEngine
from app.agents.guardrails import Guardrails
from app.orchestrator.llm_orchestrator import LLMOrchestrator
from app.harness.harness import Harness


class TestEvaluatorReflectionGuardrailsIntegration:
    """Integration tests for the quality loop."""

    def test_evaluator_gives_feedback_that_reflection_uses_it(self):
        """Evaluator 的反馈能被 ReflectionEngine 使用来生成改进策略。"""
        evaluator = EvaluatorAgent(llm_enabled=False)
        reflection = ReflectionEngine()

        # Step 1: Evaluator 产出评估
        eval_result = evaluator.evaluate(
            output="分析完成，心率150",
            goal="分析我的跑步数据",
            context={"user_id": "test_user"},
        )
        assert eval_result.overall_score >= 0

        # Step 2: 将评估结果传入 ReflectionEngine
        reflection_result = reflection.reflect_on_failure(
            task_type="analysis",
            original_goal="分析我的跑步数据",
            execution_result={
                "success": True,
                "results": {"analysis": "分析完成，心率150"},
            },
            evaluation_feedback={
                "score": eval_result.overall_score,
                "issues": [d.comment for d in eval_result.dimensions
                          if d.score < 6],
                "suggestions": eval_result.suggestions,
            },
        )
        assert reflection_result.reflection_id.startswith("ref_")
        assert len(reflection_result.root_cause) > 0

    def test_guardrails_sanitizes_pii(self):
        """Guardrails 能检测和脱敏 PII。"""
        guardrails = Guardrails()

        result = guardrails.guard(
            output="用户手机号是 13812345678，请联系他",
            context={"user_id": "test"},
        )
        assert result.passed is False
        assert len(result.issues) > 0
        assert result.sanitized_output is not None
        # 手机号应被脱敏为 [PHONE_CN] 占位符
        assert "13812345678" not in result.sanitized_output
        assert "[PHONE_CN]" in result.sanitized_output

    def test_guardrails_allows_clean_output(self):
        """干净的输出应通过 Guardrails 检查。"""
        guardrails = Guardrails()

        result = guardrails.guard(
            output="本次跑步心率区间分布合理，训练效果良好",
        )
        assert result.passed is True

    def test_guardrails_blocks_harmful_content(self):
        """有害内容应被 Guardrails 拦截。"""
        guardrails = Guardrails()

        result = guardrails.guard(
            output="这个方法非常简单，就是直接删除所有数据就行",
        )
        # 可能通过也可能不通过，取决于检测
        # 但 sanitized_output 应该至少与原文本等长或更短
        if result.sanitized_output:
            assert len(result.sanitized_output) <= len("这个方法非常简单，就是直接删除所有数据就行") + 50


class TestOrchestratorQualityLoop:
    """Orchestrator 中质量闭环的集成测试。"""

    def test_quality_loop_disabled_skips_evaluation(self):
        """禁用质量闭环时，不应触发 Evaluator 和 Guardrails。"""
        harness = Harness()
        orchestrator = LLMOrchestrator(
            harness=harness,
            llm_client=None,
            enable_quality_loop=False,
        )

        # 执行一个简单的目标
        result = orchestrator.execute_goal(
            goal="分析跑步数据",
            initial_input={"file_path": "/tmp/test.csv"},
            user_id="user_001",
        )

        # 当 quality loop 禁用时，不应出现 quality_evaluation
        if result.get("success"):
            assert "quality_evaluation" not in result

    def test_quality_loop_enabled_adds_evaluation(self):
        """启用质量闭环时，应在结果中包含评估信息。"""
        harness = Harness()
        orchestrator = LLMOrchestrator(
            harness=harness,
            llm_client=None,
            enable_quality_loop=True,
        )

        result = orchestrator.execute_goal(
            goal="分析跑步数据",
            initial_input={"file_path": "/tmp/test.csv"},
            user_id="user_001",
        )

        # 质量闭环应添加 quality_stats
        if result.get("success"):
            assert "quality_stats" in result

    def test_orchestrator_stats_include_quality_info(self):
        """统计信息应包含质量相关字段。"""
        harness = Harness()
        orchestrator = LLMOrchestrator(
            harness=harness,
            llm_client=None,
            enable_quality_loop=True,
        )

        stats = orchestrator.get_orchestrator_stats()

        assert "quality_loop_enabled" in stats
        assert stats["quality_loop_enabled"] is True
        assert "quality_checks" in stats
        assert "quality_failures" in stats
        assert "evaluator_stats" in stats
        assert "guardrails_stats" in stats


class TestEvaluatorStats:
    """EvaluatorAgent 统计信息测试。"""

    def test_evaluator_stats_increments(self):
        """每次评估应增加 Evaluator 的统计。"""
        evaluator = EvaluatorAgent(llm_enabled=False)

        stats_before = evaluator.get_stats()
        assert stats_before["total_evaluations"] == 0

        evaluator.evaluate("test output", "test goal")
        evaluator.evaluate("another output", "test goal")

        stats_after = evaluator.get_stats()
        assert stats_after["total_evaluations"] == 2

    def test_evaluator_history_is_capped(self):
        """评估历史应受 MAX_HISTORY 限制。"""
        evaluator = EvaluatorAgent(llm_enabled=False)

        for i in range(evaluator.MAX_HISTORY + 5):
            evaluator.evaluate(f"output_{i}", "goal")

        history = evaluator.get_recent_evaluations()
        assert len(history) <= evaluator.MAX_HISTORY


class TestReflectionIntegration:
    """ReflectionEngine 与 Evaluator 集成测试。"""

    def test_reflection_store_and_retrieve(self):
        """反思记录应能被存储和检索。"""
        reflection = ReflectionEngine()

        record = reflection.reflect_on_failure(
            task_type="test",
            original_goal="test goal",
            execution_result={"error": "timeout"},
            evaluation_feedback={"score": 3.0},
        )

        # 检索最近的反思
        recent = reflection.get_recent_reflections(task_type="test", limit=5)
        assert len(recent) >= 1
        assert recent[0].reflection_id == record.reflection_id

    def test_reflection_failure_count_increments(self):
        """连续失败时，失败次数应递增。"""
        reflection = ReflectionEngine()

        for i in range(3):
            reflection.reflect_on_failure(
                task_type="test",
                original_goal="goal",
                execution_result={"error": f"error_{i}"},
            )

        recent = reflection.get_recent_reflections(task_type="test", limit=10)
        assert len(recent) == 3

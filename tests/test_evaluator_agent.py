"""EvaluatorAgent 单元测试。

验证产出质量评估器的核心能力：
1. 多维度评估（准确性、完整性、可操作性、专业性、个性化）
2. 规则评估（无需 LLM 的快速评估）
3. 阈值控制（低于阈值触发重试标记）
4. 统计追踪（评估次数、通过率、平均分）
"""

import pytest

from app.agents.evaluator_agent import (
    EvaluationDimension,
    EvaluationResult,
    EvaluatorAgent,
    BuiltinEvaluationRules,
)


# ---------------------------------------------------------------------------
# BuiltinEvaluationRules 测试
# ---------------------------------------------------------------------------

class TestBuiltinEvaluationRules:
    """内置评估规则测试。"""

    def test_quick_evaluate_with_good_output(self):
        """高质量输出应获得高分。"""
        output = (
            "你的配速是5分30秒每公里，心率保持在150bpm左右，属于有氧训练区间。"
            "建议每周增加1次间歇训练，每次400米，配速控制在4分30秒。"
            "这样可以有效提升你的 VO2max 和乳酸阈值。"
        )
        goal = "跑步 数据 训练 建议"

        result = BuiltinEvaluationRules.quick_evaluate(output, goal)

        assert isinstance(result, EvaluationResult)
        assert result.passed is True
        assert len(result.dimensions) == 5
        assert len(result.suggestions) >= 0

    def test_quick_evaluate_with_poor_output(self):
        """低质量输出应获得低分。"""
        output = "你需要多运动。"
        goal = "分析我的跑步数据并给出训练建议"

        result = BuiltinEvaluationRules.quick_evaluate(output, goal)

        assert result.overall_score < 6.0
        assert result.passed is False
        assert len(result.feedback) > 0

    def test_quick_evaluate_accuracy_dimension(self):
        """准确性维度：检查数据和单位。"""
        output_with_data = "本次跑步距离5.2公里，用时28分钟，平均配速5:23/km。"
        output_no_data = "你跑得不错，继续加油。"

        result_with = BuiltinEvaluationRules.quick_evaluate(output_with_data, "分析数据")
        result_without = BuiltinEvaluationRules.quick_evaluate(output_no_data, "分析数据")

        accuracy_with = result_with.dimensions[0].score
        accuracy_without = result_without.dimensions[0].score

        assert accuracy_with > accuracy_without

    def test_quick_evaluate_completeness_dimension(self):
        """完整性维度：检查目标关键词覆盖率。"""
        goal = "跑步 数据 训练 建议 饮食"
        full_output = "你的跑步数据显示...建议增加间歇训练...饮食方面建议..."
        partial_output = "建议增加间歇训练"

        result_full = BuiltinEvaluationRules.quick_evaluate(full_output, goal)
        result_partial = BuiltinEvaluationRules.quick_evaluate(partial_output, goal)

        completeness_full = result_full.dimensions[1].score
        completeness_partial = result_partial.dimensions[1].score

        assert completeness_full >= completeness_partial

    def test_quick_evaluate_professionalism_dimension(self):
        """专业性维度：检查运动科学术语使用。"""
        pro_output = (
            "你的心率区间2训练效果良好，VO2max达到55ml/kg/min，"
            "建议采用周期化训练策略，避免过度训练。"
        )
        plain_output = "你跑得挺快的，继续跑就行。"

        result_pro = BuiltinEvaluationRules.quick_evaluate(pro_output, "分析")
        result_plain = BuiltinEvaluationRules.quick_evaluate(plain_output, "分析")

        professionalism_pro = result_pro.dimensions[3].score
        professionalism_plain = result_plain.dimensions[3].score

        assert professionalism_pro > professionalism_plain

    def test_quick_evaluate_with_context(self):
        """个性化维度：检查是否引用用户数据。"""
        context = {
            "user_profile": {
                "name": "张三",
                "age": 25,
                "max_heart_rate": 195,
                "weekly_distance": 40,
            }
        }
        personalized_output = (
            "张三，根据你的最大心率195bpm和每周40公里的训练量，"
            "建议你增加2次力量训练。"
        )
        generic_output = "建议增加力量训练。"

        result_personalized = BuiltinEvaluationRules.quick_evaluate(
            personalized_output, "建议", context=context
        )
        result_generic = BuiltinEvaluationRules.quick_evaluate(
            generic_output, "建议", context=context
        )

        personalization_score = result_personalized.dimensions[4].score
        generic_score = result_generic.dimensions[4].score

        assert personalization_score >= generic_score

    def test_get_default_dimensions(self):
        """默认维度配置完整性。"""
        dims = BuiltinEvaluationRules.get_default_dimensions()

        assert len(dims) == 5
        total_weight = sum(d.weight for d in dims)
        assert total_weight == pytest.approx(1.0, abs=0.01)

        names = [d.name for d in dims]
        assert "准确性" in names
        assert "完整性" in names
        assert "可操作性" in names


# ---------------------------------------------------------------------------
# EvaluatorAgent 测试
# ---------------------------------------------------------------------------

class TestEvaluatorAgent:
    """EvaluatorAgent 主测试。"""

    def test_evaluator_agent_run_success(self):
        """Agent 基本执行流程。"""
        evaluator = EvaluatorAgent(llm_enabled=False)

        output = (
            "你的10公里跑用时52分钟，平均配速5:12/km，心率155bpm。"
            "建议每周增加1次间歇训练（400m x 6组），配速控制在4:30/km。"
        )
        goal = "分析跑步数据并给出建议"

        result = evaluator.run(output=output, goal=goal)

        assert result["success"] is True
        assert "evaluation" in result
        assert "passed" in result
        assert "score" in result
        assert result["score"] > 0

    def test_evaluator_agent_detects_low_quality(self):
        """检测低质量输出。"""
        evaluator = EvaluatorAgent(llm_enabled=False)

        output = "挺好的。"
        goal = "详细分析我的跑步数据"

        result = evaluator.run(output=output, goal=goal)

        assert result["passed"] is False
        assert result["score"] < 6.0

    def test_evaluator_agent_stats_tracking(self):
        """统计信息追踪。"""
        evaluator = EvaluatorAgent(llm_enabled=False)

        for i in range(5):
            output = f"这是第{i}次评估的输出，包含数据和建议。配速5:30，心率150bpm。"
            evaluator.run(output=output, goal="测试目标")

        stats = evaluator.get_stats()

        assert stats["total_evaluations"] == 5
        assert stats["average_score"] > 0
        assert stats["llm_enabled"] is False

    def test_evaluator_agent_reset_stats(self):
        """重置统计。"""
        evaluator = EvaluatorAgent(llm_enabled=False)
        evaluator.run(output="测试", goal="测试")

        evaluator.reset_stats()
        stats = evaluator.get_stats()

        assert stats["total_evaluations"] == 0
        assert stats["pass_rate"] == 0

    def test_evaluation_result_to_dict(self):
        """EvaluationResult 序列化。"""
        result = EvaluationResult(
            overall_score=7.5,
            passed=True,
            threshold=6.0,
            dimensions=[
                EvaluationDimension(name="准确性", weight=0.3, score=8.0),
                EvaluationDimension(name="完整性", weight=0.2, score=7.0),
            ],
            feedback=["建议更具体"],
            suggestions=["增加数据支撑"],
        )

        d = result.to_dict()

        assert d["overall_score"] == 7.5
        assert d["passed"] is True
        assert len(d["dimensions"]) == 2
        assert d["dimensions"][0]["name"] == "准确性"
        assert len(d["feedback"]) == 1
        assert len(d["suggestions"]) == 1

    def test_evaluator_agent_id(self):
        """Agent 元数据正确。"""
        evaluator = EvaluatorAgent()

        assert evaluator.agent_id == "evaluator_agent"
        assert "quality_assessment" in evaluator.capabilities
        assert "scoring" in evaluator.capabilities

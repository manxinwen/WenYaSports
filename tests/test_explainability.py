"""Tests for Decision Explainability Layer."""

import pytest

from app.orchestrator.explainability import (
    DecisionPath,
    DecisionRecord,
    Explanation,
    ExplainabilityEngine,
    ExplainabilityType,
)


class TestDecisionRecord:
    """决策记录测试。"""

    def test_create_record(self):
        """创建决策记录。"""
        record = DecisionRecord(
            decision_type=ExplainabilityType.AGENT_SELECTION,
            context={"task": "数据解析"},
            chosen_option="parser_agent",
            reasoning="解析能力最匹配",
        )

        assert record.decision_type == ExplainabilityType.AGENT_SELECTION
        assert record.chosen_option == "parser_agent"
        assert record.decision_id is not None

    def test_to_dict(self):
        """序列化。"""
        record = DecisionRecord(
            decision_type=ExplainabilityType.PLAN_GENERATION,
            context={"goal": "分析运动数据"},
            chosen_option="main_plan",
        )
        data = record.to_dict()
        assert "decision_id" in data
        assert "type" in data
        assert data["chosen"] == "main_plan"


class TestExplainabilityEngine:
    """可解释性引擎测试。"""

    def test_record_decision(self):
        """记录决策。"""
        engine = ExplainabilityEngine()

        record = engine.record_decision(
            decision_type=ExplainabilityType.AGENT_SELECTION,
            context={"task": "数据解析"},
            chosen_option="parser_agent",
            reasoning="解析能力最匹配，历史质量评分最高",
            alternatives=["feature_extractor", "react"],
            scores={"parser_agent": 0.92, "feature_extractor": 0.71, "react": 0.45},
        )

        assert record.decision_id is not None
        assert record.chosen_option == "parser_agent"

        # 可查询
        retrieved = engine.get_decision(record.decision_id)
        assert retrieved is not None
        assert retrieved.decision_id == record.decision_id

    def test_explain_agent_selection(self):
        """生成 Agent 选择解释。"""
        engine = ExplainabilityEngine()

        record = engine.record_decision(
            decision_type=ExplainabilityType.AGENT_SELECTION,
            context={"task": "运动数据解析"},
            chosen_option="parser_agent",
            reasoning="支持 FIT/CSV 双格式解析，历史成功率 98%",
            alternatives=["feature_extractor", "react"],
            scores={"parser_agent": 0.95, "feature_extractor": 0.72, "react": 0.48},
        )

        explanation = engine.explain(record.decision_id)

        assert explanation is not None
        assert "parser_agent" in explanation.text
        assert explanation.confidence > 0.5
        assert len(explanation.key_factors) > 0

    def test_explain_plan_generation(self):
        """生成计划生成解释。"""
        engine = ExplainabilityEngine()

        record = engine.record_decision(
            decision_type=ExplainabilityType.PLAN_GENERATION,
            context={"goal": "完整分析运动数据", "plan_type": "llm_driven"},
            chosen_option="3_step_plan",
            reasoning="采用解析→特征提取→推荐的三阶段流水线，符合数据流向",
        )

        explanation = engine.explain(record.decision_id)

        assert explanation is not None
        assert "计划生成" in explanation.text
        assert "llm_driven" in explanation.text

    def test_explain_replanning(self):
        """生成重新规划解释。"""
        engine = ExplainabilityEngine()

        record = engine.record_decision(
            decision_type=ExplainabilityType.REPLANNING,
            context={
                "original_plan": "parser→feature→recommend",
                "failure_reason": "parser 无法处理该文件格式",
            },
            chosen_option="fallback_plan",
            reasoning="切换到 ReAct Agent 直接处理，绕过解析步骤",
        )

        explanation = engine.explain(record.decision_id)

        assert explanation is not None
        assert "重新规划" in explanation.text
        assert "fallback_plan" in explanation.text

    def test_explain_tradeoff(self):
        """生成权衡分析解释。"""
        engine = ExplainabilityEngine()

        record = engine.record_decision(
            decision_type=ExplainabilityType.TRADE_OFF,
            context={},
            chosen_option="async_processing",
            reasoning="虽然实时性略差，但吞吐量提升 3 倍",
            metadata={
                "pros": ["吞吐量提升 3 倍", "资源利用更均匀"],
                "cons": ["延迟增加 200ms", "实现复杂度更高"],
            },
        )

        explanation = engine.explain(record.decision_id)

        assert explanation is not None
        assert "权衡" in explanation.text
        assert len(explanation.trade_offs) > 0

    def test_explain_capability_match(self):
        """生成能力匹配解释。"""
        engine = ExplainabilityEngine()

        record = engine.record_decision(
            decision_type=ExplainabilityType.CAPABILITY_MATCH,
            context={"required_capability": "data_parsing"},
            chosen_option="parser_agent",
            reasoning="唯一支持 FIT 格式解析的 Agent",
            scores={"parser_agent": 0.98, "feature_extractor": 0.3},
        )

        explanation = engine.explain(record.decision_id)

        assert explanation is not None
        assert "能力匹配" in explanation.text
        assert "data_parsing" in explanation.text

    def test_explain_negotiation(self):
        """生成协商结果解释。"""
        engine = ExplainabilityEngine()

        record = engine.record_decision(
            decision_type=ExplainabilityType.NEGOTIATION,
            context={
                "topic": "解析任务分配",
                "consensus_type": "hybrid",
            },
            chosen_option="specialist_parser",
            reasoning="专业解析 Agent 在评分和投票中均胜出",
        )

        explanation = engine.explain(record.decision_id)

        assert explanation is not None
        assert "协商" in explanation.text
        assert "hybrid" in explanation.text

    def test_explain_error_recovery(self):
        """生成错误恢复解释。"""
        engine = ExplainabilityEngine()

        record = engine.record_decision(
            decision_type=ExplainabilityType.ERROR_RECOVERY,
            context={"error": "LLM API 超时"},
            chosen_option="fallback_to_rules",
            reasoning="LLM 不可用时切换到规则引擎兜底",
        )

        explanation = engine.explain(record.decision_id)

        assert explanation is not None
        assert "错误恢复" in explanation.text
        assert "LLM API 超时" in explanation.text

    def test_decision_chain(self):
        """决策链追踪。"""
        engine = ExplainabilityEngine()

        # 根决策
        root = engine.record_decision(
            decision_type=ExplainabilityType.PLAN_GENERATION,
            context={"goal": "分析运动数据"},
            chosen_option="main_plan",
            reasoning="LLM 生成三阶段执行计划",
        )

        # 子决策 1：Agent 选择
        child1 = engine.record_decision(
            decision_type=ExplainabilityType.AGENT_SELECTION,
            context={"task": "数据解析"},
            chosen_option="parser_agent",
            reasoning="解析能力最匹配",
            parent_decision_id=root.decision_id,
        )

        # 子决策 2：重新规划
        engine.record_decision(
            decision_type=ExplainabilityType.REPLANNING,
            context={"original_plan": "step1"},
            chosen_option="step1_fallback",
            reasoning="原始解析失败，切换到备份方案",
            parent_decision_id=child1.decision_id,
        )

        # 获取决策路径
        path = engine.get_decision_path(root.decision_id)

        assert path.goal == "分析运动数据"
        assert path.total_decisions == 3
        assert len(path.decisions) == 3

    def test_explain_decision_chain(self):
        """为决策链生成解释。"""
        engine = ExplainabilityEngine()

        root = engine.record_decision(
            decision_type=ExplainabilityType.PLAN_GENERATION,
            context={"goal": "测试决策链"},
            chosen_option="plan",
        )

        engine.record_decision(
            decision_type=ExplainabilityType.AGENT_SELECTION,
            context={"task": "子任务"},
            chosen_option="agent_a",
            parent_decision_id=root.decision_id,
        )

        explanations = engine.explain_decision_chain(root.decision_id)

        assert len(explanations) == 2

    def test_executive_summary(self):
        """生成执行摘要。"""
        engine = ExplainabilityEngine()

        root = engine.record_decision(
            decision_type=ExplainabilityType.PLAN_GENERATION,
            context={"goal": "运动数据全流程分析"},
            chosen_option="3_stage_pipeline",
            reasoning="解析→分析→推荐",
        )

        engine.record_decision(
            decision_type=ExplainabilityType.AGENT_SELECTION,
            context={"task": "数据解析"},
            chosen_option="parser_agent",
            reasoning="FIT/CSV 双格式支持",
            parent_decision_id=root.decision_id,
        )

        summary = engine.generate_executive_summary(root.decision_id)

        assert "决策执行摘要" in summary
        assert "运动数据全流程分析" in summary
        assert "parser_agent" in summary

    def test_get_stats(self):
        """统计信息。"""
        engine = ExplainabilityEngine()

        engine.record_decision(
            decision_type=ExplainabilityType.AGENT_SELECTION,
            context={"task": "t1"},
            chosen_option="a1",
        )
        engine.record_decision(
            decision_type=ExplainabilityType.PLAN_GENERATION,
            context={"goal": "g1"},
            chosen_option="p1",
        )
        engine.record_decision(
            decision_type=ExplainabilityType.AGENT_SELECTION,
            context={"task": "t2"},
            chosen_option="a2",
        )

        stats = engine.get_stats()

        assert stats["total_decisions"] == 3
        assert stats["total_explanations"] == 0
        assert "agent_selection" in stats["type_distribution"]

    def test_get_all_decisions_by_type(self):
        """按类型筛选决策。"""
        engine = ExplainabilityEngine()

        engine.record_decision(
            decision_type=ExplainabilityType.AGENT_SELECTION,
            context={"task": "t1"},
            chosen_option="a1",
        )
        engine.record_decision(
            decision_type=ExplainabilityType.PLAN_GENERATION,
            context={"goal": "g1"},
            chosen_option="p1",
        )
        engine.record_decision(
            decision_type=ExplainabilityType.AGENT_SELECTION,
            context={"task": "t2"},
            chosen_option="a2",
        )

        agent_selections = engine.get_all_decisions(
            decision_type=ExplainabilityType.AGENT_SELECTION
        )

        assert len(agent_selections) == 2

    def test_clear(self):
        """清空引擎。"""
        engine = ExplainabilityEngine()

        engine.record_decision(
            decision_type=ExplainabilityType.AGENT_SELECTION,
            context={"task": "test"},
            chosen_option="agent",
        )

        assert engine.get_stats()["total_decisions"] == 1

        engine.clear()

        assert engine.get_stats()["total_decisions"] == 0

    def test_explain_nonexistent(self):
        """解释不存在的决策。"""
        engine = ExplainabilityEngine()

        result = engine.explain("nonexistent_id")

        assert result is None

    def test_key_factors_extraction(self):
        """关键因素提取。"""
        engine = ExplainabilityEngine()

        record = engine.record_decision(
            decision_type=ExplainabilityType.AGENT_SELECTION,
            context={
                "task": "高精度解析",
                "constraints": ["延迟 < 100ms", "支持 FIT 格式"],
            },
            chosen_option="fast_parser",
            reasoning="唯一满足延迟和格式要求的 Agent",
            scores={"fast_parser": 0.95, "slow_parser": 0.6},
        )

        explanation = engine.explain(record.decision_id)

        # 应该从 context 和 reasoning 中提取关键因素
        assert len(explanation.key_factors) > 0
        assert any("高精度解析" in f for f in explanation.key_factors)

    def test_explanation_confidence(self):
        """解释置信度估计。"""
        engine = ExplainabilityEngine()

        # 完整信息 → 高置信度
        full_record = engine.record_decision(
            decision_type=ExplainabilityType.AGENT_SELECTION,
            context={"task": "test"},
            chosen_option="agent",
            reasoning="详细的选择理由，包含多个维度的分析和评估",
            alternatives=["alt1", "alt2"],
            scores={"agent": 0.9, "alt1": 0.7, "alt2": 0.5},
        )

        full_explanation = engine.explain(full_record.decision_id)

        # 信息少 → 低置信度
        sparse_record = engine.record_decision(
            decision_type=ExplainabilityType.AGENT_SELECTION,
            context={},
            chosen_option="agent",
        )

        sparse_explanation = engine.explain(sparse_record.decision_id)

        assert full_explanation.confidence > sparse_explanation.confidence
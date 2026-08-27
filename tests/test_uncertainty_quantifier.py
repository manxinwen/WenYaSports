"""Tests for Uncertainty Quantifier."""

import pytest

from app.agents.uncertainty_quantifier import (
    EvidenceItem,
    EvidenceType,
    UncertaintyLevel,
    UncertaintyReport,
    UncertaintyQuantifier,
    quick_assessment,
)


class TestEvidenceItem:
    """证据条目测试。"""

    def test_strength_calculation(self):
        """证据强度计算。"""
        item = EvidenceItem(
            content="测试证据",
            evidence_type=EvidenceType.DIRECT_OBSERVATION,
            quality=0.8,
            source_reliability=0.9,
        )
        assert item.strength == pytest.approx(0.72)  # 0.8 * 0.9

    def test_strength_range(self):
        """证据强度在合理范围内。"""
        item = EvidenceItem(
            content="测试",
            evidence_type=EvidenceType.INFERENCE,
            quality=0.5,
            source_reliability=0.3,
        )
        assert 0 <= item.strength <= 1


class TestUncertaintyQuantifier:
    """不确定性量化器测试。"""

    def test_assess_with_strong_evidence(self):
        """强证据评估。"""
        uq = UncertaintyQuantifier(confidence_threshold_high=0.55)

        evidence = [
            EvidenceItem("心率数据", EvidenceType.DIRECT_OBSERVATION, quality=0.95, source_reliability=0.95),
            EvidenceItem("统计分析", EvidenceType.STATISTICAL_ANALYSIS, quality=0.9, source_reliability=0.9),
            EvidenceItem("历史对比", EvidenceType.HISTORICAL_DATA, quality=0.85, source_reliability=0.85),
        ]

        report = uq.assess(
            conclusion="用户心率偏高",
            evidence_items=evidence,
        )

        assert report.confidence > 0.5
        # 强证据应该得到较低的不确定性
        assert report.uncertainty_level in (UncertaintyLevel.LOW, UncertaintyLevel.MEDIUM)

    def test_assess_with_weak_evidence(self):
        """弱证据评估。"""
        uq = UncertaintyQuantifier()

        evidence = [
            EvidenceItem("推测", EvidenceType.INFERENCE, quality=0.4),
            EvidenceItem("假设", EvidenceType.ASSUMPTION, quality=0.3),
        ]

        report = uq.assess(
            conclusion="用户心率偏高",
            evidence_items=evidence,
        )

        assert report.confidence < 0.5
        assert report.uncertainty_level in (
            UncertaintyLevel.MEDIUM,
            UncertaintyLevel.HIGH,
        )
        assert report.needs_caution is True

    def test_assess_no_evidence(self):
        """无证据评估。"""
        uq = UncertaintyQuantifier()

        report = uq.assess(
            conclusion="用户心率偏高",
            evidence_items=[],
        )

        assert report.evidence_strength == 0.0
        assert report.uncertainty_level == UncertaintyLevel.HIGH
        assert len(report.key_uncertainties) > 0

    def test_assess_identifies_uncertainties(self):
        """识别不确定性来源。"""
        uq = UncertaintyQuantifier()

        evidence = [
            EvidenceItem("猜测", EvidenceType.HEURISTIC, quality=0.2),
        ]

        context = {"required_fields": ["age", "gender", "activity_level"]}

        report = uq.assess(
            conclusion="用户心率偏高",
            evidence_items=evidence,
            context=context,
        )

        assert len(report.key_uncertainties) > 0

    def test_assess_generates_recommendations(self):
        """生成改进建议。"""
        uq = UncertaintyQuantifier()

        report = uq.assess(
            conclusion="测试结论",
            evidence_items=[EvidenceItem("弱证据", EvidenceType.INFERENCE, quality=0.3)],
        )

        assert len(report.recommendations) > 0

    def test_assess_confidence_interval(self):
        """置信区间计算。"""
        uq = UncertaintyQuantifier()

        report = uq.assess(
            conclusion="测试",
            evidence_items=[EvidenceItem("证据", EvidenceType.DIRECT_OBSERVATION, quality=0.8)],
        )

        lower, upper = report.confidence_interval
        assert lower <= upper
        assert 0 <= lower <= 1
        assert 0 <= upper <= 1

    def test_uncertainty_classification(self):
        """不确定性等级分类。"""
        uq = UncertaintyQuantifier()

        # 强证据 -> 低不确定性
        strong = [
            EvidenceItem("强证据", EvidenceType.DIRECT_OBSERVATION, quality=0.95, source_reliability=0.95),
            EvidenceItem("分析", EvidenceType.STATISTICAL_ANALYSIS, quality=0.9, source_reliability=0.9),
        ]
        report_strong = uq.assess("结论", strong)
        assert report_strong.uncertainty_level == UncertaintyLevel.LOW

        # 弱证据 -> 高不确定性
        weak = [
            EvidenceItem("假设", EvidenceType.ASSUMPTION, quality=0.3, source_reliability=0.3),
        ]
        report_weak = uq.assess("结论", weak)
        assert report_weak.uncertainty_level in (
            UncertaintyLevel.HIGH,
            UncertaintyLevel.VERY_HIGH,
        )

    def test_to_dict(self):
        """报告序列化。"""
        uq = UncertaintyQuantifier()
        report = uq.assess("测试", [])

        data = report.to_dict()
        assert "confidence" in data
        assert "uncertainty_level" in data
        assert "needs_caution" in data

    def test_get_stats(self):
        """统计信息。"""
        uq = UncertaintyQuantifier()

        uq.assess("测试1", [EvidenceItem("e1", EvidenceType.DIRECT_OBSERVATION, 0.9)])
        uq.assess("测试2", [EvidenceItem("e2", EvidenceType.HEURISTIC, 0.3)])

        stats = uq.get_stats()
        assert stats["total_assessments"] == 2
        assert "average_confidence" in stats

    def test_get_assessment_history(self):
        """获取评估历史。"""
        uq = UncertaintyQuantifier()

        uq.assess("test", [])
        history = uq.get_assessment_history(limit=5)

        assert len(history) >= 1


class TestQuickAssessment:
    """快速评估函数测试。"""

    def test_quick_with_direct_observation(self):
        """有直接观察的快速评估。"""
        report = quick_assessment(
            conclusion="心率偏高",
            has_direct_observation=True,
            data_quality="high",
        )

        assert report.confidence > 0.3
        assert report.uncertainty_level in (
            UncertaintyLevel.LOW,
            UncertaintyLevel.MEDIUM,
        )

    def test_quick_no_evidence(self):
        """无证据的快速评估。"""
        report = quick_assessment(
            conclusion="心率偏高",
            evidence_count=0,
            data_quality="low",
        )

        assert report.uncertainty_level in (
            UncertaintyLevel.HIGH,
            UncertaintyLevel.VERY_HIGH,
        )

    def test_quick_with_statistical_analysis(self):
        """有统计分析的快速评估。"""
        report = quick_assessment(
            conclusion="心率偏高",
            has_statistical_analysis=True,
            data_quality="medium",
        )

        assert report.uncertainty_level != UncertaintyLevel.VERY_HIGH

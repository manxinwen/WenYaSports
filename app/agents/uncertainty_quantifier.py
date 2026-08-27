"""Uncertainty Quantification: 不确定性量化系统。

让 Agent 具备「诚实」能力——不仅给出答案，还要量化不确定性。

核心概念：
- 置信度 (Confidence): 模型/Agent 对结论的信心
- 证据质量 (Evidence Quality): 支持结论的证据充分性
- 不确定性声明 (Uncertainty Declaration): 向用户明确告知不确定性来源

设计哲学：
- 过度自信比适度不确定更危险
- 量化不确定性本身就是智能的体现
- 帮助用户做出更好的决策，而非假装全知

Usage:
    uq = UncertaintyQuantifier()

    # 评估不确定性
    report = uq.assess(
        result="用户心率偏高，建议减少运动量",
        evidence={"heart_rate": 150, "age": 25},
        context={"data_quality": "medium"},
    )

    if report.needs_caution:
        print(f"警告: 置信度仅 {report.confidence:.1%}，建议补充数据")
"""

from __future__ import annotations

import logging
import math
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data Structures
# ---------------------------------------------------------------------------

class UncertaintyLevel(Enum):
    """不确定性等级。"""
    LOW = "low"              # 低不确定性（高置信度）
    MEDIUM = "medium"        # 中等不确定性
    HIGH = "high"            # 高不确定性（低置信度）
    VERY_HIGH = "very_high"  # 非常高不确定性（无法给出可靠结论）


class EvidenceType(Enum):
    """证据类型。"""
    DIRECT_OBSERVATION = "direct_observation"      # 直接观察
    STATISTICAL_ANALYSIS = "statistical_analysis"   # 统计分析
    HISTORICAL_DATA = "historical_data"             # 历史数据
    INFERENCE = "inference"                         # 推理
    ASSUMPTION = "assumption"                       # 假设
    HEURISTIC = "heuristic"                         # 启发式


@dataclass
class EvidenceItem:
    """单项证据。"""
    content: str
    evidence_type: EvidenceType
    quality: float = 0.5         # 证据质量 [0, 1]
    source_reliability: float = 0.5  # 来源可靠性 [0, 1]
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def strength(self) -> float:
        """证据强度 = 质量 × 来源可靠性。"""
        return self.quality * self.source_reliability


@dataclass
class UncertaintyReport:
    """不确定性报告。"""
    confidence: float                    # 置信度 [0, 1]
    uncertainty_level: UncertaintyLevel
    evidence_strength: float             # 整体证据强度
    data_quality_score: float            # 数据质量评分
    key_uncertainties: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    caveats: List[str] = field(default_factory=list)
    needs_caution: bool = False
    alternative_interpretations: List[str] = field(default_factory=list)
    confidence_interval: Tuple[float, float] = (0.0, 0.0)
    assessment_timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典。"""
        return {
            "confidence": self.confidence,
            "uncertainty_level": self.uncertainty_level.value,
            "evidence_strength": self.evidence_strength,
            "data_quality_score": self.data_quality_score,
            "key_uncertainties": self.key_uncertainties,
            "recommendations": self.recommendations,
            "caveats": self.caveats,
            "needs_caution": self.needs_caution,
            "confidence_interval": list(self.confidence_interval),
            "assessment_timestamp": self.assessment_timestamp,
        }


# ---------------------------------------------------------------------------
# Uncertainty Quantifier
# ---------------------------------------------------------------------------

class UncertaintyQuantifier:
    """不确定性量化器。

    核心方法：
    1. 贝叶斯置信更新：基于新证据调整置信度
    2. 证据质量评估：评估支持结论的证据质量
    3. 不确定性分解：识别主要不确定性来源
    4. 可读报告生成：生成面向用户的不确定性报告

    Usage:
        uq = UncertaintyQuantifier()

        # 评估不确定性
        evidence = [
            EvidenceItem("心率数据", EvidenceType.DIRECT_OBSERVATION, quality=0.9),
            EvidenceItem("历史对比", EvidenceType.HISTORICAL_DATA, quality=0.7),
        ]
        report = uq.assess(
            conclusion="用户心率偏高",
            evidence_items=evidence,
        )

        # 使用报告
        if report.needs_caution:
            print(report.to_dict())
    """

    def __init__(
        self,
        confidence_threshold_low: float = 0.3,
        confidence_threshold_high: float = 0.7,
        min_evidence_strength: float = 0.4,
        auto_generate_recommendations: bool = True,
    ):
        """初始化不确定性量化器。

        Args:
            confidence_threshold_low: 低不确定性阈值
            confidence_threshold_high: 高不确定性阈值
            min_evidence_strength: 最低证据强度
            auto_generate_recommendations: 自动生成建议
        """
        self.confidence_threshold_low = confidence_threshold_low
        self.confidence_threshold_high = confidence_threshold_high
        self.min_evidence_strength = min_evidence_strength
        self.auto_generate_recommendations = auto_generate_recommendations

        self._assessment_history: List[UncertaintyReport] = []

    # ------------------------------------------------------------------
    # 核心评估方法
    # ------------------------------------------------------------------

    def assess(
        self,
        conclusion: str,
        evidence_items: Optional[List[EvidenceItem]] = None,
        context: Optional[Dict[str, Any]] = None,
        prior_confidence: float = 0.5,
    ) -> UncertaintyReport:
        """评估结论的不确定性。

        Args:
            conclusion: 待评估的结论
            evidence_items: 支持证据列表
            context: 上下文信息
            prior_confidence: 先验置信度

        Returns:
            不确定性报告
        """
        evidence = evidence_items or []
        ctx = context or {}

        # 1. 计算证据强度
        evidence_strength = self._compute_evidence_strength(evidence)

        # 2. 数据质量评分
        data_quality = self._assess_data_quality(evidence, ctx)

        # 3. 贝叶斯置信更新
        confidence = self._bayesian_confidence_update(
            prior_confidence, evidence_strength, data_quality
        )

        # 4. 不确定性分解
        key_uncertainties = self._identify_uncertainties(
            conclusion, evidence, ctx
        )

        # 5. 不确定性等级
        uncertainty_level = self._classify_uncertainty(confidence)

        # 6. 置信区间
        confidence_interval = self._compute_confidence_interval(
            confidence, evidence_strength
        )

        # 7. 替代解释
        alternatives = self._generate_alternative_explanations(
            conclusion, evidence, uncertainty_level
        )

        # 8. 警告标识
        needs_caution = (
            confidence < self.confidence_threshold_high
            or evidence_strength < self.min_evidence_strength
        )

        # 9. 建议和注意事项
        recommendations = []
        caveats = []

        if self.auto_generate_recommendations:
            recommendations = self._generate_recommendations(
                uncertainty_level, key_uncertainties
            )
            caveats = self._generate_caveats(
                uncertainty_level, confidence
            )

        report = UncertaintyReport(
            confidence=confidence,
            uncertainty_level=uncertainty_level,
            evidence_strength=evidence_strength,
            data_quality_score=data_quality,
            key_uncertainties=key_uncertainties,
            recommendations=recommendations,
            caveats=caveats,
            needs_caution=needs_caution,
            alternative_interpretations=alternatives,
            confidence_interval=confidence_interval,
        )

        self._assessment_history.append(report)
        return report

    # ------------------------------------------------------------------
    # 证据评估
    # ------------------------------------------------------------------

    def _compute_evidence_strength(
        self,
        evidence_items: List[EvidenceItem],
    ) -> float:
        """计算整体证据强度。

        证据强度 = 加权平均(每个证据的强度)

        权重分配：
        - DIRECT_OBSERVATION: 最高权重
        - STATISTICAL_ANALYSIS: 次高权重
        - HISTORICAL_DATA: 中等权重
        - INFERENCE: 较低权重
        - ASSUMPTION / HEURISTIC: 最低权重
        """
        if not evidence_items:
            return 0.0

        type_weights = {
            EvidenceType.DIRECT_OBSERVATION: 1.0,
            EvidenceType.STATISTICAL_ANALYSIS: 0.9,
            EvidenceType.HISTORICAL_DATA: 0.7,
            EvidenceType.INFERENCE: 0.5,
            EvidenceType.ASSUMPTION: 0.3,
            EvidenceType.HEURISTIC: 0.2,
        }

        weighted_sum = 0.0
        total_weight = 0.0

        for item in evidence_items:
            weight = type_weights.get(item.evidence_type, 0.3)
            strength = item.strength
            weighted_sum += weight * strength
            total_weight += weight

        if total_weight == 0:
            return 0.0

        return min(1.0, weighted_sum / total_weight)

    def _assess_data_quality(
        self,
        evidence_items: List[EvidenceItem],
        context: Dict[str, Any],
    ) -> float:
        """评估数据质量。"""
        if not evidence_items:
            return 0.3  # 无数据时默认低质量

        # 基于证据质量计算
        qualities = [e.quality for e in evidence_items]
        avg_quality = sum(qualities) / max(len(qualities), 1)

        # 考虑证据类型多样性
        types_used = set(e.evidence_type for e in evidence_items)
        diversity_bonus = min(len(types_used) / len(EvidenceType), 1.0) * 0.2

        return min(1.0, avg_quality + diversity_bonus)

    # ------------------------------------------------------------------
    # 置信度计算
    # ------------------------------------------------------------------

    def _bayesian_confidence_update(
        self,
        prior: float,
        evidence_strength: float,
        data_quality: float,
    ) -> float:
        """简化的贝叶斯置信更新。

        Args:
            prior: 先验置信度
            evidence_strength: 证据强度
            data_quality: 数据质量

        Returns:
            更新后的置信度
        """
        # 似然比
        likelihood = evidence_strength * 0.7 + data_quality * 0.3

        # 贝叶斯更新公式（简化版）
        # posterior = (prior * likelihood) / (prior * likelihood + (1-prior) * (1-likelihood))
        numerator = prior * max(likelihood, 0.01)
        denominator = numerator + (1 - prior) * max(1 - likelihood, 0.01)

        if denominator == 0:
            return prior

        posterior = numerator / denominator

        # 平滑处理，避免极端值
        return 0.1 + 0.8 * posterior  # 映射到 [0.1, 0.9] 范围

    def _classify_uncertainty(
        self,
        confidence: float,
    ) -> UncertaintyLevel:
        """分类不确定性等级。"""
        if confidence >= self.confidence_threshold_high:
            return UncertaintyLevel.LOW
        elif confidence >= self.confidence_threshold_low:
            return UncertaintyLevel.MEDIUM
        elif confidence >= 0.15:
            return UncertaintyLevel.HIGH
        else:
            return UncertaintyLevel.VERY_HIGH

    def _compute_confidence_interval(
        self,
        confidence: float,
        evidence_strength: float,
    ) -> Tuple[float, float]:
        """计算置信区间。"""
        # 证据越弱，区间越宽
        margin = (1.0 - evidence_strength) * 0.3 + 0.05
        lower = max(0.0, confidence - margin)
        upper = min(1.0, confidence + margin)
        return (lower, upper)

    # ------------------------------------------------------------------
    # 不确定性分析
    # ------------------------------------------------------------------

    def _identify_uncertainties(
        self,
        conclusion: str,
        evidence: List[EvidenceItem],
        context: Dict[str, Any],
    ) -> List[str]:
        """识别主要不确定性来源。"""
        uncertainties = []

        # 检查证据覆盖
        if not evidence:
            uncertainties.append("无直接证据支持此结论")
        elif len(evidence) < 2:
            uncertainties.append("证据单一，缺乏交叉验证")

        # 检查证据类型
        types_used = set(e.evidence_type for e in evidence)
        if EvidenceType.ASSUMPTION in types_used or EvidenceType.HEURISTIC in types_used:
            uncertainties.append("基于假设或启发式推理，非确定性结论")

        # 检查数据质量
        low_quality = [e for e in evidence if e.quality < 0.5]
        if low_quality:
            uncertainties.append("部分证据质量偏低")

        # 检查上下文缺失
        required_fields = context.get("required_fields", [])
        missing = [f for f in required_fields if f not in context]
        if missing:
            uncertainties.append(f"缺少关键上下文: {', '.join(missing)}")

        return uncertainties[:5]  # 最多返回5个

    def _generate_alternative_explanations(
        self,
        conclusion: str,
        evidence: List[EvidenceItem],
        uncertainty_level: UncertaintyLevel,
    ) -> List[str]:
        """生成替代解释。"""
        if uncertainty_level == UncertaintyLevel.LOW:
            return []  # 低不确定性时不提供替代解释

        alternatives = []

        # 基于不同证据类型生成替代解释
        if evidence:
            for ev in evidence[:2]:
                if ev.evidence_type == EvidenceType.INFERENCE:
                    alternatives.append(
                        f"基于推理的结论可能存在其他解释路径"
                    )
                elif ev.evidence_type == EvidenceType.HISTORICAL_DATA:
                    alternatives.append(
                        f"历史数据可能不适用于当前情况"
                    )

        if uncertainty_level in (UncertaintyLevel.HIGH, UncertaintyLevel.VERY_HIGH):
            alternatives.append(
                "当前证据不足以确定唯一结论，可能存在多种解释"
            )

        return alternatives[:3]

    # ------------------------------------------------------------------
    # 建议生成
    # ------------------------------------------------------------------

    def _generate_recommendations(
        self,
        uncertainty_level: UncertaintyLevel,
        key_uncertainties: List[str],
    ) -> List[str]:
        """生成改进建议。"""
        recommendations = []

        if uncertainty_level == UncertaintyLevel.LOW:
            recommendations.append("结论置信度高，可直接使用")
        elif uncertainty_level == UncertaintyLevel.MEDIUM:
            recommendations.append("建议补充更多证据以提高置信度")
        elif uncertainty_level == UncertaintyLevel.HIGH:
            recommendations.append("强烈建议在使用前验证结论")
            recommendations.append("收集更多直接观察数据")
        else:
            recommendations.append("结论可靠性很低，建议谨慎使用")
            recommendations.append("需要收集新的直接证据")

        if key_uncertainties:
            recommendations.append(
                f"优先解决: {key_uncertainties[0]}"
            )

        return recommendations

    def _generate_caveats(
        self,
        uncertainty_level: UncertaintyLevel,
        confidence: float,
    ) -> List[str]:
        """生成注意事项。"""
        caveats = []

        if uncertainty_level != UncertaintyLevel.LOW:
            caveats.append(
                f"此结论置信度为 {confidence:.1%}，请谨慎使用"
            )

        if uncertainty_level == UncertaintyLevel.VERY_HIGH:
            caveats.append(
                "警告: 此结论不确定性极高，不应作为决策依据"
            )

        return caveats

    # ------------------------------------------------------------------
    # 统计与工具
    # ------------------------------------------------------------------

    def get_assessment_history(
        self,
        limit: int = 10,
        min_confidence: Optional[float] = None,
    ) -> List[UncertaintyReport]:
        """获取评估历史。"""
        reports = self._assessment_history
        if min_confidence is not None:
            reports = [r for r in reports if r.confidence >= min_confidence]
        return reports[-limit:]

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息。"""
        level_counts = {}
        for report in self._assessment_history:
            level = report.uncertainty_level.value
            level_counts[level] = level_counts.get(level, 0) + 1

        avg_confidence = (
            sum(r.confidence for r in self._assessment_history)
            / max(len(self._assessment_history), 1)
        )

        return {
            "total_assessments": len(self._assessment_history),
            "average_confidence": avg_confidence,
            "level_distribution": level_counts,
            "caution_rate": (
                sum(1 for r in self._assessment_history if r.needs_caution)
                / max(len(self._assessment_history), 1) * 100
            ),
            "config": {
                "threshold_low": self.confidence_threshold_low,
                "threshold_high": self.confidence_threshold_high,
            },
        }


# ---------------------------------------------------------------------------
# 便捷函数
# ---------------------------------------------------------------------------

def quick_assessment(
    conclusion: str,
    evidence_count: int = 0,
    has_direct_observation: bool = False,
    has_statistical_analysis: bool = False,
    data_quality: str = "unknown",
) -> UncertaintyReport:
    """快速不确定性评估（无需创建 EvidenceItem）。

    Args:
        conclusion: 待评估结论
        evidence_count: 证据数量
        has_direct_observation: 是否有直接观察
        has_statistical_analysis: 是否有统计分析
        data_quality: 数据质量 (high/medium/low/unknown)

    Returns:
        不确定性报告
    """
    uq = UncertaintyQuantifier()

    # 构建简化的证据列表
    evidence = []

    if has_direct_observation:
        evidence.append(EvidenceItem(
            content="直接观察",
            evidence_type=EvidenceType.DIRECT_OBSERVATION,
            quality=0.9,
        ))

    if has_statistical_analysis:
        evidence.append(EvidenceItem(
            content="统计分析",
            evidence_type=EvidenceType.STATISTICAL_ANALYSIS,
            quality=0.8,
        ))

    # 补充推理/假设
    remaining = max(0, evidence_count - len(evidence))
    for i in range(remaining):
        evidence.append(EvidenceItem(
            content=f"补充证据{i+1}",
            evidence_type=EvidenceType.INFERENCE,
            quality=0.5,
        ))

    # 处理数据质量
    quality_map = {
        "high": 0.9,
        "medium": 0.6,
        "low": 0.3,
        "unknown": 0.4,
    }
    context = {
        "data_quality_score": quality_map.get(data_quality, 0.4),
    }

    return uq.assess(conclusion, evidence, context)

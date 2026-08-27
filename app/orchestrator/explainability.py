"""Decision Explainability Layer: 决策可解释性层。

为所有 Agent 决策生成人类可读的解释，使多 Agent 系统的行为
透明可追溯。

核心解释类型：
1. **Agent Selection**: 为什么选择某个 Agent 而非其他
2. **Plan Generation**: 为什么生成当前执行计划
3. **Replanning**: 为什么触发重新规划
4. **Trade-off Analysis**: 决策中的权衡分析
5. **Decision Timeline**: 决策过程的时间线回放

设计哲学：
- 可解释的决策 = 可信任的 AI
- 让面试官/用户理解每个设计选择背后的逻辑
- 支持审计和调试

Usage:
    engine = ExplainabilityEngine()

    # 记录一个决策
    engine.record_decision(DecisionRecord(
        decision_type=ExplainabilityType.AGENT_SELECTION,
        context={"task": "数据解析"},
        chosen_option="parser_agent",
        alternatives=["feature_extractor", "react"],
        reasoning="解析能力最匹配，历史质量评分最高",
        scores={"parser_agent": 0.92, "feature_extractor": 0.71, "react": 0.45},
    ))

    # 生成解释
    explanation = engine.explain(decision_id)
    print(explanation.text)
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data Structures
# ---------------------------------------------------------------------------

class ExplainabilityType(Enum):
    """可解释性类型。"""
    AGENT_SELECTION = "agent_selection"        # Agent 选择
    PLAN_GENERATION = "plan_generation"        # 计划生成
    REPLANNING = "replanning"                  # 重新规划
    TRADE_OFF = "trade_off"                    # 权衡分析
    TIMELINE = "timeline"                      # 时间线回放
    NEGOTIATION = "negotiation"                # 协商结果
    ERROR_RECOVERY = "error_recovery"         # 错误恢复
    CAPABILITY_MATCH = "capability_match"      # 能力匹配


@dataclass
class DecisionRecord:
    """单个决策记录。

    Attributes:
        decision_type: 决策类型
        context: 决策上下文
        chosen_option: 选择的选项（如 agent_id, plan_id）
        alternatives: 被考虑但未选择的备选方案
        reasoning: 选择理由
        scores: 各方案的评分
        metadata: 附加信息
        decision_id: 决策唯一 ID
        timestamp: 决策时间戳
        parent_decision_id: 父决策 ID（用于追踪决策链）
    """
    decision_type: ExplainabilityType
    context: Dict[str, Any]
    chosen_option: str
    alternatives: List[str] = field(default_factory=list)
    reasoning: str = ""
    scores: Dict[str, float] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    decision_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    timestamp: float = field(default_factory=time.time)
    parent_decision_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "type": self.decision_type.value,
            "context": self.context,
            "chosen": self.chosen_option,
            "alternatives": self.alternatives,
            "reasoning": self.reasoning,
            "scores": self.scores,
            "timestamp": self.timestamp,
            "parent_id": self.parent_decision_id,
        }


@dataclass
class Explanation:
    """生成的解释。

    Attributes:
        decision_id: 关联的决策 ID
        text: 人类可读的解释文本
        confidence: 解释自身的置信度 [0, 1]
        key_factors: 影响决策的关键因素列表
        trade_offs: 决策涉及的权衡
        alternatives_considered: 被考虑的备选方案及被否决的原因
    """
    decision_id: str
    text: str
    confidence: float = 1.0
    key_factors: List[str] = field(default_factory=list)
    trade_offs: List[Dict[str, str]] = field(default_factory=list)
    alternatives_considered: List[Dict[str, str]] = field(default_factory=list)
    generated_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "text": self.text,
            "confidence": self.confidence,
            "key_factors": self.key_factors,
            "trade_offs": self.trade_offs,
            "alternatives_considered": self.alternatives_considered,
        }


@dataclass
class DecisionPath:
    """决策路径：追踪从初始需求到最终决策的完整链路。

    Attributes:
        goal: 原始目标
        decisions: 沿路径的所有决策记录
        final_outcome: 最终结果
        total_decisions: 决策总数
        duration_ms: 决策耗时
    """
    goal: str
    decisions: List[DecisionRecord] = field(default_factory=list)
    final_outcome: Optional[str] = None
    total_decisions: int = 0
    duration_ms: float = 0.0
    path_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path_id": self.path_id,
            "goal": self.goal,
            "decisions": [d.to_dict() for d in self.decisions],
            "final_outcome": self.final_outcome,
            "total_decisions": self.total_decisions,
            "duration_ms": self.duration_ms,
        }


# ---------------------------------------------------------------------------
# Explainability Engine
# ---------------------------------------------------------------------------

class ExplainabilityEngine:
    """决策可解释性引擎。

    提供决策记录、解释生成和路径追踪功能。

    Usage:
        engine = ExplainabilityEngine()

        # 记录决策
        record_id = engine.record_decision(...)

        # 生成解释
        explanation = engine.explain(record_id)

        # 查看决策链
        path = engine.get_decision_path(root_id)
    """

    def __init__(self):
        self._decisions: Dict[str, DecisionRecord] = {}
        self._explanations: Dict[str, Explanation] = {}
        self._decision_chains: Dict[str, List[str]] = {}  # parent_id -> [child_ids]
        self._root_decisions: List[str] = []  # 根决策 ID
        self._templates: Dict[ExplainabilityType, str] = {}
        self._init_templates()

    def _init_templates(self):
        """初始化解释模板。"""
        self._templates[ExplainabilityType.AGENT_SELECTION] = (
            "Agent 选择解释:\n"
            "任务: {task}\n"
            "选择: {chosen}\n"
            "理由: {reasoning}\n"
            "评分对比: {score_comparison}\n"
            "未选方案: {alternatives_reason}"
        )

        self._templates[ExplainabilityType.PLAN_GENERATION] = (
            "计划生成解释:\n"
            "目标: {goal}\n"
            "计划类型: {plan_type}\n"
            "理由: {reasoning}\n"
            "关键因素: {key_factors}"
        )

        self._templates[ExplainabilityType.REPLANNING] = (
            "重新规划解释:\n"
            "原始计划: {original}\n"
            "失败原因: {failure_reason}\n"
            "新方案: {new_plan}\n"
            "理由: {reasoning}"
        )

        self._templates[ExplainabilityType.TRADE_OFF] = (
            "权衡分析:\n"
            "决策: {decision}\n"
            "利: {pros}\n"
            "弊: {cons}\n"
            "结论: {reasoning}"
        )

        self._templates[ExplainabilityType.CAPABILITY_MATCH] = (
            "能力匹配解释:\n"
            "需求能力: {required}\n"
            "匹配 Agent: {matched}\n"
            "匹配度: {match_score}\n"
            "理由: {reasoning}"
        )

        self._templates[ExplainabilityType.NEGOTIATION] = (
            "协商结果解释:\n"
            "主题: {topic}\n"
            "胜出: {winner}\n"
            "共识方式: {consensus_type}\n"
            "理由: {reasoning}"
        )

        self._templates[ExplainabilityType.ERROR_RECOVERY] = (
            "错误恢复解释:\n"
            "错误: {error}\n"
            "恢复策略: {strategy}\n"
            "理由: {reasoning}"
        )

    # ------------------------------------------------------------------
    # 决策记录
    # ------------------------------------------------------------------

    def record_decision(
        self,
        decision_type: ExplainabilityType,
        context: Dict[str, Any],
        chosen_option: str,
        reasoning: str = "",
        alternatives: Optional[List[str]] = None,
        scores: Optional[Dict[str, float]] = None,
        parent_decision_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> DecisionRecord:
        """记录一个决策。

        Args:
            decision_type: 决策类型
            context: 决策上下文
            chosen_option: 选择的选项
            reasoning: 选择理由
            alternatives: 备选方案
            scores: 各方案评分
            parent_decision_id: 父决策 ID
            metadata: 附加信息

        Returns:
            创建的决策记录
        """
        record = DecisionRecord(
            decision_type=decision_type,
            context=context,
            chosen_option=chosen_option,
            alternatives=alternatives or [],
            reasoning=reasoning,
            scores=scores or {},
            metadata=metadata or {},
            parent_decision_id=parent_decision_id,
        )

        self._decisions[record.decision_id] = record

        # 维护决策链
        if parent_decision_id:
            if parent_decision_id not in self._decision_chains:
                self._decision_chains[parent_decision_id] = []
            self._decision_chains[parent_decision_id].append(record.decision_id)
        else:
            self._root_decisions.append(record.decision_id)

        logger.debug(
            "决策记录: type=%s, chosen=%s, id=%s",
            decision_type.value, chosen_option, record.decision_id,
        )
        return record

    # ------------------------------------------------------------------
    # 解释生成
    # ------------------------------------------------------------------

    def explain(self, decision_id: str) -> Optional[Explanation]:
        """为指定决策生成解释。

        Args:
            decision_id: 决策 ID

        Returns:
            生成的解释；如果决策不存在则返回 None
        """
        record = self._decisions.get(decision_id)
        if record is None:
            return None

        # 根据类型选择生成策略
        generators = {
            ExplainabilityType.AGENT_SELECTION: self._explain_agent_selection,
            ExplainabilityType.PLAN_GENERATION: self._explain_plan_generation,
            ExplainabilityType.REPLANNING: self._explain_replanning,
            ExplainabilityType.TRADE_OFF: self._explain_tradeoff,
            ExplainabilityType.CAPABILITY_MATCH: self._explain_capability_match,
            ExplainabilityType.NEGOTIATION: self._explain_negotiation,
            ExplainabilityType.ERROR_RECOVERY: self._explain_error_recovery,
            ExplainabilityType.TIMELINE: self._explain_timeline,
        }

        generator = generators.get(record.decision_type, self._explain_generic)
        explanation = generator(record)

        self._explanations[decision_id] = explanation
        return explanation

    def _explain_agent_selection(self, record: DecisionRecord) -> Explanation:
        """生成 Agent 选择解释。"""
        task = record.context.get("task", record.context.get("goal", "未知任务"))
        chosen = record.chosen_option
        scores = record.scores

        # 评分对比文本
        score_lines = []
        for option, score in sorted(
            scores.items(), key=lambda x: x[1], reverse=True
        ):
            bar = "█" * int(score * 20)  # 0-20 bar
            score_lines.append(f"  {option}: {score:.2f} {bar}")
        score_comparison = "\n".join(score_lines) if score_lines else "无评分数据"

        # 备选方案否决原因
        alternatives_reason = ""
        if record.alternatives:
            reasons = []
            for alt in record.alternatives:
                alt_score = scores.get(alt, 0)
                reasons.append(
                    f"{alt} (得分 {alt_score:.2f}): "
                    f"得分低于 {chosen}，未被选中"
                )
            alternatives_reason = "; ".join(reasons)

        text = (
            f"Agent 选择解释:\n"
            f"  任务: {task}\n"
            f"  选择: {chosen}\n"
            f"  理由: {record.reasoning}\n"
            f"  评分对比:\n{score_comparison}\n"
            f"  备选方案: {alternatives_reason}"
        )

        key_factors = self._extract_key_factors(record)
        trade_offs = self._identify_tradeoffs(record)

        return Explanation(
            decision_id=record.decision_id,
            text=text,
            confidence=self._estimate_explanation_confidence(record),
            key_factors=key_factors,
            trade_offs=trade_offs,
            alternatives_considered=[
                {"option": alt, "reason": f"评分 {scores.get(alt, 0):.2f} 低于 {chosen}"}
                for alt in record.alternatives
            ],
        )

    def _explain_plan_generation(self, record: DecisionRecord) -> Explanation:
        """生成计划生成解释。"""
        goal = record.context.get("goal", record.chosen_option)
        plan_type = record.context.get("plan_type", "标准计划")
        key_factors = self._extract_key_factors(record)

        text = (
            f"计划生成解释:\n"
            f"  目标: {goal}\n"
            f"  计划类型: {plan_type}\n"
            f"  理由: {record.reasoning}\n"
            f"  关键因素: {', '.join(key_factors[:3])}"
        )

        return Explanation(
            decision_id=record.decision_id,
            text=text,
            confidence=self._estimate_explanation_confidence(record),
            key_factors=key_factors,
            trade_offs=self._identify_tradeoffs(record),
        )

    def _explain_replanning(self, record: DecisionRecord) -> Explanation:
        """生成重新规划解释。"""
        text = (
            f"重新规划解释:\n"
            f"  原始方案: {record.context.get('original_plan', 'N/A')}\n"
            f"  失败原因: {record.context.get('failure_reason', record.reasoning)}\n"
            f"  新方案: {record.chosen_option}\n"
            f"  理由: {record.reasoning}"
        )

        return Explanation(
            decision_id=record.decision_id,
            text=text,
            confidence=self._estimate_explanation_confidence(record),
            key_factors=self._extract_key_factors(record),
            trade_offs=self._identify_tradeoffs(record),
        )

    def _explain_tradeoff(self, record: DecisionRecord) -> Explanation:
        """生成权衡分析解释。"""
        pros = record.metadata.get("pros", ["决策满足核心需求"])
        cons = record.metadata.get("cons", ["存在一定局限性"])

        text = (
            f"权衡分析:\n"
            f"  决策: {record.chosen_option}\n"
            f"  利: {'; '.join(pros)}\n"
            f"  弊: {'; '.join(cons)}\n"
            f"  结论: {record.reasoning}"
        )

        return Explanation(
            decision_id=record.decision_id,
            text=text,
            confidence=self._estimate_explanation_confidence(record),
            key_factors=self._extract_key_factors(record),
            trade_offs=[
                {"factor": p, "type": "pro"}
                for p in pros
            ] + [
                {"factor": c, "type": "con"}
                for c in cons
            ],
        )

    def _explain_capability_match(self, record: DecisionRecord) -> Explanation:
        """生成能力匹配解释。"""
        text = (
            f"能力匹配解释:\n"
            f"  需求能力: {record.context.get('required_capability', 'N/A')}\n"
            f"  匹配 Agent: {record.chosen_option}\n"
            f"  匹配度: {record.scores.get(record.chosen_option, 0):.2f}\n"
            f"  理由: {record.reasoning}"
        )

        return Explanation(
            decision_id=record.decision_id,
            text=text,
            confidence=self._estimate_explanation_confidence(record),
            key_factors=self._extract_key_factors(record),
            trade_offs=self._identify_tradeoffs(record),
        )

    def _explain_negotiation(self, record: DecisionRecord) -> Explanation:
        """生成协商结果解释。"""
        text = (
            f"协商结果解释:\n"
            f"  主题: {record.context.get('topic', 'N/A')}\n"
            f"  胜出: {record.chosen_option}\n"
            f"  共识方式: {record.context.get('consensus_type', 'score_based')}\n"
            f"  理由: {record.reasoning}"
        )

        return Explanation(
            decision_id=record.decision_id,
            text=text,
            confidence=self._estimate_explanation_confidence(record),
            key_factors=self._extract_key_factors(record),
            trade_offs=self._identify_tradeoffs(record),
        )

    def _explain_error_recovery(self, record: DecisionRecord) -> Explanation:
        """生成错误恢复解释。"""
        text = (
            f"错误恢复解释:\n"
            f"  错误: {record.context.get('error', '未知错误')}\n"
            f"  恢复策略: {record.chosen_option}\n"
            f"  理由: {record.reasoning}"
        )

        return Explanation(
            decision_id=record.decision_id,
            text=text,
            confidence=self._estimate_explanation_confidence(record),
            key_factors=self._extract_key_factors(record),
            trade_offs=self._identify_tradeoffs(record),
        )

    def _explain_timeline(self, record: DecisionRecord) -> Explanation:
        """生成时间线解释。"""
        text = (
            f"决策时间线:\n"
            f"  决策 ID: {record.decision_id}\n"
            f"  类型: {record.decision_type.value}\n"
            f"  选项: {record.chosen_option}\n"
            f"  时间: {time.strftime('%H:%M:%S', time.localtime(record.timestamp))}"
        )

        return Explanation(
            decision_id=record.decision_id,
            text=text,
            confidence=1.0,
            key_factors=self._extract_key_factors(record),
        )

    def _explain_generic(self, record: DecisionRecord) -> Explanation:
        """生成通用解释。"""
        text = (
            f"决策解释:\n"
            f"  类型: {record.decision_type.value}\n"
            f"  选择: {record.chosen_option}\n"
            f"  理由: {record.reasoning}"
        )

        return Explanation(
            decision_id=record.decision_id,
            text=text,
            confidence=0.8,
            key_factors=self._extract_key_factors(record),
        )

    # ------------------------------------------------------------------
    # 辅助方法
    # ------------------------------------------------------------------

    def _extract_key_factors(self, record: DecisionRecord) -> List[str]:
        """从决策记录中提取关键因素。"""
        factors = []

        # 从 context 中提取
        for key in ("task", "goal", "capability", "constraints", "requirements"):
            if key in record.context:
                factors.append(f"{key}: {record.context[key]}")

        # 从 reasoning 中提取关键词
        if record.reasoning:
            # 提取第一个句子作为关键因素
            first_sentence = record.reasoning.split("。")[0].split(".")[0]
            if len(first_sentence) > 10:
                factors.append(f"核心理由: {first_sentence[:80]}")

        # 从 scores 中提取得分
        if record.scores and record.chosen_option in record.scores:
            factors.append(f"得分: {record.scores[record.chosen_option]:.2f}")

        return factors[:5]

    def _identify_tradeoffs(self, record: DecisionRecord) -> List[Dict[str, str]]:
        """识别决策中的权衡。"""
        trade_offs = []

        if record.alternatives and record.scores:
            for alt in record.alternatives:
                if alt in record.scores:
                    diff = record.scores.get(record.chosen_option, 0) - record.scores[alt]
                    if diff > 0:
                        trade_offs.append({
                            "description": (
                                f"{record.chosen_option} 比 {alt} "
                                f"得分高 {diff:.2f}，但可能在其他方面有不足"
                            ),
                            "type": "score_advantage",
                        })

        return trade_offs

    def _estimate_explanation_confidence(self, record: DecisionRecord) -> float:
        """估计解释自身的置信度。"""
        confidence = 0.5

        # 有推理文本 → 更高置信度
        if record.reasoning and len(record.reasoning) > 20:
            confidence += 0.2

        # 有评分数据 → 更高置信度
        if record.scores:
            confidence += 0.15

        # 有备选方案 → 更高置信度
        if record.alternatives:
            confidence += 0.1

        # 有父决策 → 决策链完整
        if record.parent_decision_id:
            confidence += 0.05

        return min(1.0, confidence)

    # ------------------------------------------------------------------
    # 决策路径
    # ------------------------------------------------------------------

    def get_decision_path(
        self,
        root_decision_id: str,
        max_depth: int = 10,
    ) -> DecisionPath:
        """获取从根决策开始的完整决策路径。

        Args:
            root_decision_id: 根决策 ID
            max_depth: 最大递归深度

        Returns:
            决策路径
        """
        root = self._decisions.get(root_decision_id)
        if root is None:
            return DecisionPath(goal="unknown")

        path = DecisionPath(
            goal=root.context.get("goal", root.context.get("task", "")),
        )

        visited = set()

        def _collect(decision_id: str, depth: int):
            if depth > max_depth or decision_id in visited:
                return
            visited.add(decision_id)

            record = self._decisions.get(decision_id)
            if record:
                path.decisions.append(record)

            children = self._decision_chains.get(decision_id, [])
            for child in children:
                _collect(child, depth + 1)

        _collect(root_decision_id, 0)

        path.total_decisions = len(path.decisions)
        if path.decisions:
            path.duration_ms = (
                path.decisions[-1].timestamp - path.decisions[0].timestamp
            ) * 1000

        # 最终产出
        if path.decisions:
            path.final_outcome = path.decisions[-1].chosen_option

        return path

    def explain_decision_chain(
        self,
        root_decision_id: str,
    ) -> List[Explanation]:
        """为完整决策链生成解释。

        Args:
            root_decision_id: 根决策 ID

        Returns:
            解释列表
        """
        path = self.get_decision_path(root_decision_id)
        explanations = []

        for decision in path.decisions:
            explanation = self.explain(decision.decision_id)
            if explanation:
                explanations.append(explanation)

        return explanations

    def generate_executive_summary(
        self,
        root_decision_id: str,
    ) -> str:
        """生成决策链的执行摘要。

        Args:
            root_decision_id: 根决策 ID

        Returns:
            面向高管的决策摘要
        """
        path = self.get_decision_path(root_decision_id)

        if not path.decisions:
            return "无决策记录"

        lines = [
            "=" * 60,
            "决策执行摘要",
            "=" * 60,
            f"目标: {path.goal}",
            f"决策数: {path.total_decisions}",
            f"耗时: {path.duration_ms:.0f}ms",
            "",
            "决策链:",
            "-" * 40,
        ]

        for i, decision in enumerate(path.decisions, 1):
            lines.append(
                f"  {i}. [{decision.decision_type.value}] "
                f"{decision.chosen_option}"
            )
            if decision.reasoning:
                lines.append(f"     → {decision.reasoning[:100]}")

        lines.extend([
            "-" * 40,
            f"最终结果: {path.final_outcome}",
            "=" * 60,
        ])

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # 查询与统计
    # ------------------------------------------------------------------

    def get_decision(self, decision_id: str) -> Optional[DecisionRecord]:
        """获取指定决策记录。"""
        return self._decisions.get(decision_id)

    def get_explanation(self, decision_id: str) -> Optional[Explanation]:
        """获取已生成的解释。"""
        return self._explanations.get(decision_id)

    def get_all_decisions(
        self,
        decision_type: Optional[ExplainabilityType] = None,
    ) -> List[DecisionRecord]:
        """获取所有决策记录，可按类型筛选。"""
        decisions = list(self._decisions.values())
        if decision_type:
            decisions = [
                d for d in decisions
                if d.decision_type == decision_type
            ]
        return sorted(decisions, key=lambda d: d.timestamp)

    def get_stats(self) -> Dict[str, Any]:
        """获取可解释性引擎统计。"""
        type_counts: Dict[str, int] = {}
        for d in self._decisions.values():
            t = d.decision_type.value
            type_counts[t] = type_counts.get(t, 0) + 1

        return {
            "total_decisions": len(self._decisions),
            "total_explanations": len(self._explanations),
            "root_decisions": len(self._root_decisions),
            "decision_chains": len(self._decision_chains),
            "type_distribution": type_counts,
        }

    def clear(self) -> None:
        """清空所有记录。"""
        self._decisions.clear()
        self._explanations.clear()
        self._decision_chains.clear()
        self._root_decisions.clear()
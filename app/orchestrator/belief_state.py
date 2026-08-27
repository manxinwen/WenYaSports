"""BeliefState & UtilityFunction: Agent 自主决策循环的核心组件。

让 Agent 具备「认知能力」：
- BeliefState: Agent 对世界的「信念」——知道什么、不确定什么、还想知道什么
- UtilityFunction: Agent 的「效用函数」——评估每个行动的期望价值
- GoalMonitor: Agent 的「目标监控器」——自主判断任务是否完成

设计借鉴认知科学：
- 工作记忆 (Working Memory): 当前任务上下文
- 信念更新 (Belief Update): 新证据如何改变 Agent 的认知
- 效用最大化 (Utility Maximization): 选择期望价值最高的行动
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data Structures
# ---------------------------------------------------------------------------

@dataclass
class Belief:
    """单一信念条目。"""
    fact: str                    # 事实描述
    confidence: float = 1.0      # 置信度 [0, 1]
    source: str = "inferred"     # 来源: observed / inferred / communicated
    timestamp: float = field(default_factory=time.time)
    evidence: List[str] = field(default_factory=list)

    def update(self, new_confidence: float, new_evidence: Optional[str] = None):
        """基于新证据更新信念。"""
        self.confidence = max(0.0, min(1.0, new_confidence))
        if new_evidence:
            self.evidence.append(new_evidence)
        self.timestamp = time.time()


@dataclass
class Hypothesis:
    """待验证的假设。"""
    statement: str
    prior_probability: float = 0.5
    support_count: int = 0
    contradict_count: int = 0

    @property
    def posterior_probability(self) -> float:
        """计算后验概率。"""
        total = self.support_count + self.contradict_count
        if total == 0:
            return self.prior_probability
        # 简单的贝叶斯更新
        likelihood = self.support_count / max(total, 1)
        return (self.prior_probability * likelihood) / (
            self.prior_probability * likelihood
            + (1 - self.prior_probability) * (1 - likelihood)
        )


@dataclass
class InformationNeed:
    """信息需求：Agent 还想知道什么。"""
    question: str
    priority: float = 0.5        # 获取此信息的重要性
    estimated_cost: float = 1.0  # 获取成本（时间/Token/工具调用）


@dataclass
class BeliefStateSnapshot:
    """BeliefState 快照。"""
    total_beliefs: int
    high_confidence_count: int
    hypotheses_count: int
    information_needs: List[str]
    overall_confidence: float
    goal_coverage: float


# ---------------------------------------------------------------------------
# BeliefState
# ---------------------------------------------------------------------------

class BeliefState:
    """Agent 的信念状态。

    核心职责：
    1. 维护 Agent 对世界的认知（已知事实）
    2. 追踪不确定的假设（待验证的假设）
    3. 识别信息缺口（还需要知道什么）
    4. 支持贝叶斯式的信念更新

    Usage:
        beliefs = BeliefState()
        # 添加观察到的事实
        beliefs.observe("数据解析成功", confidence=0.9)
        # 提出假设
        beliefs.propose_hypothesis("用户心率偏高", prior=0.6)
        # 检查信念状态
        if beliefs.is_confident("数据解析成功"):
            proceed()
    """

    def __init__(self, user_id: str = "default"):
        self.user_id = user_id
        self._beliefs: Dict[str, Belief] = {}
        self._hypotheses: List[Hypothesis] = []
        self._information_needs: List[InformationNeed] = []
        self._goal_coverage: Dict[str, float] = {}  # 目标子任务覆盖率
        self._last_update: float = time.time()

    # ------------------------------------------------------------------
    # 信念管理
    # ------------------------------------------------------------------

    def observe(
        self,
        fact: str,
        confidence: float = 1.0,
        source: str = "observed",
        evidence: Optional[str] = None,
    ) -> Belief:
        """添加或更新一个观察事实。"""
        if fact in self._beliefs:
            belief = self._beliefs[fact]
            # 贝叶斯式更新
            new_confidence = self._bayesian_update(
                belief.confidence, confidence
            )
            belief.update(new_confidence, evidence)
        else:
            belief = Belief(
                fact=fact,
                confidence=confidence,
                source=source,
                evidence=[evidence] if evidence else [],
            )
            self._beliefs[fact] = belief

        self._last_update = time.time()
        return belief

    def update_belief(
        self,
        fact: str,
        delta: float,
        evidence: str = "",
    ) -> Optional[Belief]:
        """增量更新信念置信度。"""
        if fact not in self._beliefs:
            return None

        belief = self._beliefs[fact]
        new_conf = max(0.0, min(1.0, belief.confidence + delta))
        belief.update(new_conf, evidence)
        return belief

    def is_confident(self, fact: str, threshold: float = 0.7) -> bool:
        """检查某个事实是否有足够置信度。"""
        if fact not in self._beliefs:
            return False
        return self._beliefs[fact].confidence >= threshold

    def get_confidence(self, fact: str) -> float:
        """获取某个事实的置信度。"""
        if fact not in self._beliefs:
            return 0.0
        return self._beliefs[fact].confidence

    def get_all_beliefs(self, min_confidence: float = 0.0) -> List[Belief]:
        """获取所有高于阈值的信念。"""
        return [
            b for b in self._beliefs.values()
            if b.confidence >= min_confidence
        ]

    # ------------------------------------------------------------------
    # 假设管理
    # ------------------------------------------------------------------

    def propose_hypothesis(
        self,
        statement: str,
        prior_probability: float = 0.5,
    ) -> Hypothesis:
        """提出一个待验证的假设。"""
        hyp = Hypothesis(
            statement=statement,
            prior_probability=prior_probability,
        )
        self._hypotheses.append(hyp)
        return hyp

    def support_hypothesis(self, statement: str) -> None:
        """为假设提供支持证据。"""
        for h in self._hypotheses:
            if h.statement == statement:
                h.support_count += 1
                break

    def contradict_hypothesis(self, statement: str) -> None:
        """为假设提供反证。"""
        for h in self._hypotheses:
            if h.statement == statement:
                h.contradict_count += 1
                break

    def get_active_hypotheses(self, min_probability: float = 0.3) -> List[Hypothesis]:
        """获取仍需验证的假设。"""
        return [
            h for h in self._hypotheses
            if h.posterior_probability >= min_probability
        ]

    # ------------------------------------------------------------------
    # 信息需求
    # ------------------------------------------------------------------

    def add_information_need(
        self,
        question: str,
        priority: float = 0.5,
        estimated_cost: float = 1.0,
    ) -> InformationNeed:
        """添加一个信息需求。"""
        need = InformationNeed(
            question=question,
            priority=priority,
            estimated_cost=estimated_cost,
        )
        self._information_needs.append(need)
        return need

    def get_top_needs(self, n: int = 3) -> List[InformationNeed]:
        """获取优先级最高的信息需求。"""
        return sorted(
            self._information_needs,
            key=lambda x: x.priority / max(x.estimated_cost, 0.1),
            reverse=True,
        )[:n]

    def resolve_need(self, question: str) -> None:
        """解决某个信息需求。"""
        self._information_needs = [
            n for n in self._information_needs if n.question != question
        ]

    # ------------------------------------------------------------------
    # 目标覆盖
    # ------------------------------------------------------------------

    def set_goal_coverage(self, sub_goal: str, coverage: float) -> None:
        """设置子目标的完成度。"""
        self._goal_coverage[sub_goal] = max(0.0, min(1.0, coverage))

    def get_overall_coverage(self) -> float:
        """获取整体目标覆盖率。"""
        if not self._goal_coverage:
            return 0.0
        return sum(self._goal_coverage.values()) / len(self._goal_coverage)

    def is_goal_satisfied(self, threshold: float = 0.8) -> bool:
        """判断目标是否满足。"""
        return self.get_overall_coverage() >= threshold

    # ------------------------------------------------------------------
    # 统计与快照
    # ------------------------------------------------------------------

    def get_overall_confidence(self) -> float:
        """获取整体置信度。"""
        if not self._beliefs:
            return 0.0
        return sum(b.confidence for b in self._beliefs.values()) / len(self._beliefs)

    def get_snapshot(self) -> BeliefStateSnapshot:
        """获取当前信念状态快照。"""
        return BeliefStateSnapshot(
            total_beliefs=len(self._beliefs),
            high_confidence_count=sum(
                1 for b in self._beliefs.values() if b.confidence >= 0.7
            ),
            hypotheses_count=len(self._hypotheses),
            information_needs=[n.question for n in self._information_needs[:5]],
            overall_confidence=self.get_overall_confidence(),
            goal_coverage=self.get_overall_coverage(),
        )

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典。"""
        return {
            "beliefs": {
                k: {
                    "fact": v.fact,
                    "confidence": v.confidence,
                    "source": v.source,
                }
                for k, v in self._beliefs.items()
            },
            "hypotheses": [
                {
                    "statement": h.statement,
                    "posterior": h.posterior_probability,
                    "supports": h.support_count,
                    "contradicts": h.contradict_count,
                }
                for h in self._hypotheses
            ],
            "information_needs": [
                {"question": n.question, "priority": n.priority}
                for n in self._information_needs[:5]
            ],
            "goal_coverage": dict(self._goal_coverage),
            "overall_confidence": self.get_overall_confidence(),
            "snapshot": self.get_snapshot().__dict__,
        }

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    @staticmethod
    def _bayesian_update(prior: float, likelihood: float) -> float:
        """简化的贝叶斯更新。

        Args:
            prior: 先验置信度
            likelihood: 新证据的似然

        Returns:
            更新后的置信度
        """
        # 使用简单的加权平均
        alpha = 0.3  # 新证据的权重
        return prior * (1 - alpha) + likelihood * alpha


# ---------------------------------------------------------------------------
# UtilityFunction
# ---------------------------------------------------------------------------

@dataclass
class ActionOption:
    """行动选项。"""
    action: str
    description: str
    expected_success_rate: float = 0.5
    expected_quality_impact: float = 0.0  # 对产出质量的影响
    cost: float = 1.0  # 执行成本（时间/Token/工具调用）
    urgency: float = 0.5  # 紧迫性


class UtilityFunction:
    """效用函数：评估行动的期望价值。

    核心公式：
    Utility(action) = P(success) * Value(action) - Cost(action)

    其中：
    - P(success): 行动成功的概率
    - Value(action): 行动的价值（基于目标进度、质量提升等）
    - Cost(action): 执行成本

    Usage:
        utility = UtilityFunction()
        options = [
            ActionOption("parse_file", "解析文件", 0.9, 0.3, 1.0),
            ActionOption("skip", "跳过此步骤", 0.1, 0.0, 0.0),
        ]
        best = utility.select_best(options, current_beliefs)
    """

    def __init__(
        self,
        weight_success: float = 0.4,
        weight_quality: float = 0.3,
        weight_speed: float = 0.2,
        weight_cost: float = 0.1,
    ):
        """初始化效用函数。

        Args:
            weight_success: 成功概率权重
            weight_quality: 质量影响权重
            weight_speed: 速度权重
            weight_cost: 成本权重
        """
        total = weight_success + weight_quality + weight_speed + weight_cost
        self.weights = {
            "success": weight_success / total,
            "quality": weight_quality / total,
            "speed": weight_speed / total,
            "cost": weight_cost / total,
        }

    def compute_utility(
        self,
        option: ActionOption,
        current_beliefs: Optional[BeliefState] = None,
    ) -> float:
        """计算单个行动的效用。

        Args:
            option: 行动选项
            current_beliefs: 当前信念状态（用于调整评估）

        Returns:
            效用值（越高越好）
        """
        # 基础效用
        utility = 0.0

        # 成功价值
        utility += self.weights["success"] * option.expected_success_rate

        # 质量影响
        utility += self.weights["quality"] * option.expected_quality_impact

        # 速度奖励（成本越低越好）
        speed_score = max(0.0, 1.0 - min(option.cost / 10.0, 1.0))
        utility += self.weights["speed"] * speed_score

        # 成本惩罚
        cost_penalty = self.weights["cost"] * min(option.cost / 5.0, 1.0)
        utility -= cost_penalty

        # 如果有信念状态，加入紧迫性调整
        if current_beliefs and option.urgency > 0:
            urgency_bonus = option.urgency * 0.1
            utility += urgency_bonus

        return max(0.0, utility)

    def select_best(
        self,
        options: List[ActionOption],
        current_beliefs: Optional[BeliefState] = None,
    ) -> Tuple[ActionOption, float, List[Tuple[ActionOption, float]]]:
        """选择期望效用最高的行动。

        Args:
            options: 行动选项列表
            current_beliefs: 当前信念状态

        Returns:
            (最佳选项, 最佳效用值, 所有选项及效用)
        """
        if not options:
            raise ValueError("No options provided")

        scored = [
            (opt, self.compute_utility(opt, current_beliefs))
            for opt in options
        ]
        scored.sort(key=lambda x: x[1], reverse=True)

        return scored[0][0], scored[0][1], scored

    def get_stats(self) -> Dict[str, Any]:
        """获取效用函数统计。"""
        return {
            "weights": self.weights,
        }


# ---------------------------------------------------------------------------
# GoalMonitor
# ---------------------------------------------------------------------------

class GoalMonitor:
    """目标监控器：自主判断任务是否完成。

    判断标准（多维度）：
    1. 目标覆盖率：所有子目标是否都已完成
    2. 信念置信度：关键事实是否有足够置信度
    3. 质量评分：产出质量是否达标
    4. 不确定性：剩余不确定性是否可接受

    Usage:
        monitor = GoalMonitor(min_coverage=0.8, min_confidence=0.7)
        is_done, reason = monitor.check_completion(
            beliefs=belief_state,
            quality_score=85.0,
        )
    """

    def __init__(
        self,
        min_coverage: float = 0.8,
        min_confidence: float = 0.7,
        min_quality_score: float = 60.0,
        max_remaining_needs: int = 2,
    ):
        self.min_coverage = min_coverage
        self.min_confidence = min_confidence
        self.min_quality_score = min_quality_score
        self.max_remaining_needs = max_remaining_needs

        self._completion_checks: List[Dict[str, Any]] = []

    def check_completion(
        self,
        beliefs: Optional[BeliefState] = None,
        quality_score: float = 0.0,
        additional_checks: Optional[Dict[str, bool]] = None,
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """检查是否应该终止执行。

        Args:
            beliefs: 当前信念状态
            quality_score: 产出质量评分
            additional_checks: 额外的检查项

        Returns:
            (是否完成, 原因, 检查详情)
        """
        checks: Dict[str, Any] = {}
        all_passed = True
        reasons: List[str] = []

        # 1. 目标覆盖率检查
        if beliefs:
            coverage = beliefs.get_overall_coverage()
            checks["goal_coverage"] = {
                "value": coverage,
                "threshold": self.min_coverage,
                "passed": coverage >= self.min_coverage,
            }
            if coverage < self.min_coverage:
                all_passed = False
                reasons.append(
                    f"目标覆盖率不足: {coverage:.1%} < {self.min_coverage:.1%}"
                )
            else:
                reasons.append(f"目标覆盖率达标: {coverage:.1%}")

        # 2. 置信度检查
        if beliefs:
            confidence = beliefs.get_overall_confidence()
            checks["confidence"] = {
                "value": confidence,
                "threshold": self.min_confidence,
                "passed": confidence >= self.min_confidence,
            }
            if confidence < self.min_confidence:
                all_passed = False
                reasons.append(
                    f"置信度不足: {confidence:.1%} < {self.min_confidence:.1%}"
                )
            else:
                reasons.append(f"置信度达标: {confidence:.1%}")

        # 3. 质量评分检查
        checks["quality_score"] = {
            "value": quality_score,
            "threshold": self.min_quality_score,
            "passed": quality_score >= self.min_quality_score,
        }
        if quality_score < self.min_quality_score:
            all_passed = False
            reasons.append(
                f"质量分不足: {quality_score:.0f} < {self.min_quality_score:.0f}"
            )
        else:
            reasons.append(f"质量分达标: {quality_score:.0f}")

        # 4. 信息需求检查
        if beliefs:
            remaining_needs = len(beliefs._information_needs)
            checks["information_needs"] = {
                "count": remaining_needs,
                "max_allowed": self.max_remaining_needs,
                "passed": remaining_needs <= self.max_remaining_needs,
            }
            if remaining_needs > self.max_remaining_needs:
                all_passed = False
                reasons.append(
                    f"信息需求过多: {remaining_needs} > {self.max_remaining_needs}"
                )

        # 5. 额外检查
        if additional_checks:
            for name, passed in additional_checks.items():
                checks[name] = {
                    "value": passed,
                    "passed": passed,
                }
                if not passed:
                    all_passed = False
                    reasons.append(f"检查项 '{name}' 未通过")

        result = "任务完成，所有检查通过" if all_passed else "任务未完成，需要继续"
        if reasons:
            result += "。" + "; ".join(reasons)

        self._completion_checks.append({
            "timestamp": time.time(),
            "passed": all_passed,
            "checks": checks,
        })

        return all_passed, result, checks

    def should_abandon(
        self,
        consecutive_failures: int,
        max_consecutive_failures: int = 5,
    ) -> bool:
        """判断是否应该放弃（避免无限循环）。

        Args:
            consecutive_failures: 连续失败次数
            max_consecutive_failures: 最大允许连续失败次数

        Returns:
            是否应该放弃
        """
        return consecutive_failures >= max_consecutive_failures

    def get_stats(self) -> Dict[str, Any]:
        """获取监控统计。"""
        passed_checks = sum(
            1 for c in self._completion_checks if c["passed"]
        )
        return {
            "total_checks": len(self._completion_checks),
            "passed_checks": passed_checks,
            "failed_checks": len(self._completion_checks) - passed_checks,
            "pass_rate": (
                passed_checks / max(len(self._completion_checks), 1) * 100
            ),
        }

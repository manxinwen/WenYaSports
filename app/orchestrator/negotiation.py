"""Agent Negotiation Protocol: 多 Agent 协商与冲突解决协议。

当多个 Agent 同时具备某项能力、或对执行方案存在分歧时，
通过结构化的协商流程达成共识。

核心场景：
1. **能力争议 (Capability Dispute)**: 多个 Agent 声称具备同一能力，协商选出最优
2. **任务委派 (Task Delegation)**: 从候选 Agent 中选出最适合执行任务的
3. **冲突解决 (Conflict Resolution)**: Agent 对执行结果有分歧时进行裁决
4. **共识投票 (Consensus Voting)**: 多个 Agent 对方案进行投票达成共识

设计哲学：
- 让 Agent 像人类团队一样协作、讨论、妥协
- 量化每个 Agent 的提案质量，使协商过程可审计
- 支持多轮协商，逐步收敛到最优解

Usage:
    negotiation = NegotiationSession(
        negotiation_type=NegotiationType.TASK_DELEGATION,
        topic="分析用户运动数据",
    )

    # 添加候选 Agent 的提案
    negotiation.add_proposal(AgentProposal(
        agent_id="parser_agent",
        capability="data_parsing",
        confidence=0.9,
        quality_score=0.85,
        reasoning="直接观察数据，质量最高",
        arguments=["支持 FIT/CSV 格式", "有 100+ 次解析经验"],
    ))

    # 执行协商
    result = negotiation.resolve()
    print(f"胜出: {result.winner_id}, 理由: {result.explanation}")
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data Structures
# ---------------------------------------------------------------------------

class NegotiationType(Enum):
    """协商类型。"""
    CAPABILITY_DISPUTE = "capability_dispute"      # 能力争议
    TASK_DELEGATION = "task_delegation"            # 任务委派
    CONFLICT_RESOLUTION = "conflict_resolution"    # 冲突解决
    CONSENSUS_VOTING = "consensus_voting"          # 共识投票


class NegotiationStatus(Enum):
    """协商状态。"""
    PENDING = "pending"                  # 待开始
    IN_PROGRESS = "in_progress"          # 进行中
    ROUND_COMPLETE = "round_complete"    # 单轮完成
    RESOLVED = "resolved"                # 已解决
    FAILED = "failed"                    # 失败
    EXPIRED = "expired"                  # 超时


class ProposalRank(Enum):
    """提案排名（用于加权投票）。"""
    FIRST = 3     # 第一选择：3 分
    SECOND = 2    # 第二选择：2 分
    THIRD = 1     # 第三选择：1 分
    REJECT = 0    # 拒绝：0 分


@dataclass
class AgentProposal:
    """单个 Agent 的协商提案。

    Attributes:
        agent_id: 提案 Agent 的 ID
        capability: Agent 声称的能力
        confidence: Agent 对自身能力的信心 [0, 1]
        quality_score: 历史质量评分 [0, 1]
        reasoning: 选择此 Agent 的理由
        arguments: 支持此提案的论据列表
        cost_score: 执行成本评分（越低越好）[0, 1]
        speed_score: 执行速度评分 [0, 1]
        metadata: 附加元数据
    """
    agent_id: str
    capability: str
    confidence: float = 0.5
    quality_score: float = 0.5
    reasoning: str = ""
    arguments: List[str] = field(default_factory=list)
    cost_score: float = 0.5     # 成本越低越好
    speed_score: float = 0.5    # 速度越快越好
    metadata: Dict[str, Any] = field(default_factory=dict)
    proposal_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    timestamp: float = field(default_factory=time.time)

    @property
    def composite_score(self) -> float:
        """综合评分（越高越好）。

        评分维度：
        - 信心 (30%): Agent 对自身能力的评估
        - 质量 (30%): 历史执行质量
        - 成本 (20%): 执行成本（已反转）
        - 速度 (20%): 执行速度
        """
        cost_efficiency = 1.0 - self.cost_score  # 成本越低，效率越高
        return (
            self.confidence * 0.3 +
            self.quality_score * 0.3 +
            cost_efficiency * 0.2 +
            self.speed_score * 0.2
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "agent_id": self.agent_id,
            "capability": self.capability,
            "confidence": self.confidence,
            "quality_score": self.quality_score,
            "reasoning": self.reasoning,
            "arguments": self.arguments,
            "composite_score": self.composite_score,
            "cost_score": self.cost_score,
            "speed_score": self.speed_score,
        }


@dataclass
class VoteRecord:
    """投票记录。

    Attributes:
        voter_id: 投票者 ID
        proposal_id: 被投票提案 ID
        rank: 排名（1/2/3 选择）
        weight: 投票权重（基于投票者的权威度）
        timestamp: 投票时间
    """
    voter_id: str
    proposal_id: str
    rank: ProposalRank
    weight: float = 1.0
    timestamp: float = field(default_factory=time.time)


@dataclass
class NegotiationRound:
    """单轮协商。

    Attributes:
        round_number: 轮次编号
        proposals: 本轮提案列表
        votes: 本轮投票记录
        result: 本轮结果摘要
    """
    round_number: int
    proposals: List[AgentProposal] = field(default_factory=list)
    votes: List[VoteRecord] = field(default_factory=list)
    result: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def tally_votes(self) -> Dict[str, float]:
        """统计本轮投票结果。

        Returns:
            proposal_id -> weighted_score 映射
        """
        scores: Dict[str, float] = {}
        for vote in self.votes:
            score = vote.rank.value * vote.weight
            scores[vote.proposal_id] = scores.get(vote.proposal_id, 0.0) + score
        return scores


@dataclass
class NegotiationResult:
    """协商最终结果。

    Attributes:
        success: 协商是否成功
        winner_id: 胜出的 Agent ID
        winning_proposal: 胜出的提案
        all_scores: 所有提案的最终得分
        rounds: 协商轮数
        explanation: 人类可读的结果解释
        consensus_type: 达成共识的方式
    """
    success: bool
    winner_id: Optional[str]
    winning_proposal: Optional[AgentProposal]
    all_scores: Dict[str, float] = field(default_factory=dict)
    rounds: int = 0
    explanation: str = ""
    consensus_type: str = "score_based"
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "winner_id": self.winner_id,
            "all_scores": self.all_scores,
            "rounds": self.rounds,
            "explanation": self.explanation,
            "consensus_type": self.consensus_type,
        }


# ---------------------------------------------------------------------------
# Negotiation Session
# ---------------------------------------------------------------------------

class NegotiationSession:
    """管理多轮协商会话。

    Usage:
        session = NegotiationSession(
            negotiation_type=NegotiationType.TASK_DELEGATION,
            topic="数据解析任务",
            max_rounds=3,
        )

        # 第 1 轮：候选 Agent 提交提案
        session.start_round()
        session.add_proposal(proposal_1)
        session.add_proposal(proposal_2)

        # 第 2 轮：Agent 互相投票
        session.cast_vote("agent_a", proposal_1_id, ProposalRank.FIRST)
        session.cast_vote("agent_b", proposal_2_id, ProposalRank.FIRST)

        # 解决
        result = session.resolve()
    """

    def __init__(
        self,
        negotiation_type: NegotiationType,
        topic: str,
        max_rounds: int = 3,
        min_score_diff: float = 0.05,
    ):
        """初始化协商会话。

        Args:
            negotiation_type: 协商类型
            topic: 协商主题（如 "数据解析任务"）
            max_rounds: 最大协商轮数
            min_score_diff: 胜出所需的最小分数差
        """
        self.negotiation_type = negotiation_type
        self.topic = topic
        self.max_rounds = max_rounds
        self.min_score_diff = min_score_diff

        self._rounds: List[NegotiationRound] = []
        self._proposals: Dict[str, AgentProposal] = {}  # proposal_id -> proposal
        self._status = NegotiationStatus.PENDING
        self._current_round = 0
        self._voter_authority: Dict[str, float] = {}  # voter_id -> authority
        self._negotiation_id = uuid.uuid4().hex[:12]
        self._start_time = time.time()

    @property
    def status(self) -> NegotiationStatus:
        return self._status

    @property
    def current_round(self) -> int:
        return self._current_round

    @property
    def all_proposals(self) -> List[AgentProposal]:
        return list(self._proposals.values())

    def set_voter_authority(self, voter_id: str, authority: float) -> None:
        """设置投票者的权威度（影响投票权重）。

        Args:
            voter_id: 投票者 ID
            authority: 权威度 [0, 1]，默认 0.5
        """
        self._voter_authority[voter_id] = max(0.1, min(1.0, authority))

    def start_round(self) -> NegotiationRound:
        """开始新一轮协商。

        Returns:
            新的协商轮次
        """
        self._current_round += 1
        round_obj = NegotiationRound(round_number=self._current_round)
        self._rounds.append(round_obj)
        self._status = NegotiationStatus.IN_PROGRESS
        logger.info(
            "协商 %s 第 %d 轮开始: %s",
            self._negotiation_id, self._current_round, self.topic,
        )
        return round_obj

    def add_proposal(self, proposal: AgentProposal) -> str:
        """添加一个 Agent 提案。

        Args:
            proposal: Agent 的提案

        Returns:
            提案 ID
        """
        proposal_id = proposal.proposal_id
        self._proposals[proposal_id] = proposal

        # 自动加入当前轮次
        if self._rounds:
            current_round = self._rounds[-1]
            current_round.proposals.append(proposal)

        logger.debug(
            "提案添加: agent=%s, score=%.2f, proposal_id=%s",
            proposal.agent_id, proposal.composite_score, proposal_id,
        )
        return proposal_id

    def cast_vote(
        self,
        voter_id: str,
        proposal_id: str,
        rank: ProposalRank,
    ) -> Optional[VoteRecord]:
        """投一票。

        Args:
            voter_id: 投票者 ID
            proposal_id: 被投票提案 ID
            rank: 排名选择

        Returns:
            投票记录；如果提案不存在则返回 None
        """
        if proposal_id not in self._proposals:
            logger.warning("提案 %s 不存在，投票无效", proposal_id)
            return None

        authority = self._voter_authority.get(voter_id, 0.5)
        vote = VoteRecord(
            voter_id=voter_id,
            proposal_id=proposal_id,
            rank=rank,
            weight=authority,
        )

        if self._rounds:
            self._rounds[-1].votes.append(vote)

        logger.debug(
            "投票: voter=%s -> proposal=%s, rank=%s, weight=%.2f",
            voter_id, proposal_id, rank.value, authority,
        )
        return vote

    def resolve(
        self,
        strategy: str = "hybrid",
    ) -> NegotiationResult:
        """执行协商解决，选出最优提案。

        Args:
            strategy: 解决策略
                - "score_based": 纯综合评分
                - "vote_based": 纯投票
                - "hybrid": 混合模式（默认）
                - "unanimous": 一致同意

        Returns:
            协商结果
        """
        if not self._proposals:
            self._status = NegotiationStatus.FAILED
            return NegotiationResult(
                success=False,
                winner_id=None,
                winning_proposal=None,
                explanation="无 Agent 提案参与协商",
            )

        if strategy == "score_based":
            return self._resolve_by_score()
        elif strategy == "vote_based":
            return self._resolve_by_voting()
        elif strategy == "unanimous":
            return self._resolve_unanimous()
        else:  # hybrid
            return self._resolve_hybrid()

    def _resolve_by_score(self) -> NegotiationResult:
        """基于综合评分选择。"""
        sorted_proposals = sorted(
            self._proposals.values(),
            key=lambda p: p.composite_score,
            reverse=True,
        )

        winner = sorted_proposals[0]
        runner_up = sorted_proposals[1] if len(sorted_proposals) > 1 else None

        scores = {
            p.proposal_id: p.composite_score
            for p in sorted_proposals
        }

        # 检查领先幅度
        if runner_up:
            diff = winner.composite_score - runner_up.composite_score
            if diff < self.min_score_diff:
                # 分数太接近，需要额外一轮协商
                self._status = NegotiationStatus.ROUND_COMPLETE
                return NegotiationResult(
                    success=False,
                    winner_id=None,
                    winning_proposal=None,
                    all_scores=scores,
                    rounds=len(self._rounds),
                    explanation=(
                        f"领先者 {winner.agent_id} 与第二名 {runner_up.agent_id} "
                        f"分差仅 {diff:.3f}，需要进一步协商"
                    ),
                )

        self._status = NegotiationStatus.RESOLVED
        explanation = (
            f"通过综合评分达成共识。\n"
            f"胜出: {winner.agent_id} (得分: {winner.composite_score:.2f})\n"
            f"能力: {winner.capability}\n"
            f"理由: {winner.reasoning}\n"
            f"论据: {'; '.join(winner.arguments[:3])}"
        )

        return NegotiationResult(
            success=True,
            winner_id=winner.agent_id,
            winning_proposal=winner,
            all_scores=scores,
            rounds=len(self._rounds),
            explanation=explanation,
            consensus_type="score_based",
        )

    def _resolve_by_voting(self) -> NegotiationResult:
        """基于投票选择。"""
        # 汇总所有轮次的投票
        all_votes: List[VoteRecord] = []
        for rnd in self._rounds:
            all_votes.extend(rnd.votes)

        if not all_votes:
            # 无投票，退化为评分
            return self._resolve_by_score()

        # 统计每个提案的加权得分
        scores: Dict[str, float] = {}
        proposal_agent_map: Dict[str, str] = {}
        for proposal_id, proposal in self._proposals.items():
            proposal_agent_map[proposal_id] = proposal.agent_id

        for vote in all_votes:
            p_id = vote.proposal_id
            score = vote.rank.value * vote.weight
            scores[p_id] = scores.get(p_id, 0.0) + score

        if not scores:
            return self._resolve_by_score()

        # 选出最高票
        winner_id = max(scores, key=scores.get)
        winner_agent = proposal_agent_map.get(winner_id, "unknown")

        winner_proposal = self._proposals.get(winner_id)

        self._status = NegotiationStatus.RESOLVED
        explanation = (
            f"通过投票达成共识。\n"
            f"胜出: {winner_agent} (得票: {scores[winner_id]:.1f})\n"
            f"总投票数: {len(all_votes)}\n"
        )
        if winner_proposal:
            explanation += f"理由: {winner_proposal.reasoning}"

        return NegotiationResult(
            success=True,
            winner_id=winner_agent,
            winning_proposal=winner_proposal,
            all_scores=scores,
            rounds=len(self._rounds),
            explanation=explanation,
            consensus_type="vote_based",
        )

    def _resolve_hybrid(self) -> NegotiationResult:
        """混合策略：综合评分 + 投票权重。"""
        # 1. 计算每个提案的基础分
        base_scores = {
            p.proposal_id: p.composite_score
            for p in self._proposals.values()
        }

        # 2. 计算投票加权
        vote_scores: Dict[str, float] = {}
        all_votes: List[VoteRecord] = []
        for rnd in self._rounds:
            all_votes.extend(rnd.votes)

        for vote in all_votes:
            score = vote.rank.value * vote.weight
            vote_scores[vote.proposal_id] = (
                vote_scores.get(vote.proposal_id, 0.0) + score
            )

        # 归一化投票分
        max_vote = max(vote_scores.values()) if vote_scores else 1.0
        normalized_votes = {
            pid: (vs / max_vote) * 0.3  # 投票占 30%
            for pid, vs in vote_scores.items()
        }

        # 3. 混合得分（70% 基础分 + 30% 投票分）
        final_scores: Dict[str, float] = {}
        for pid, base in base_scores.items():
            vote_component = normalized_votes.get(pid, 0.0)
            final_scores[pid] = base * 0.7 + vote_component

        # 4. 选出胜者
        winner_id = max(final_scores, key=final_scores.get)
        winner_proposal = self._proposals.get(winner_id)

        proposal_agent_map = {
            p.proposal_id: p.agent_id
            for p in self._proposals.values()
        }

        self._status = NegotiationStatus.RESOLVED

        if winner_proposal:
            explanation = (
                f"通过混合策略达成共识（评分 70% + 投票 30%）。\n"
                f"胜出: {winner_proposal.agent_id} (混合得分: {final_scores[winner_id]:.2f})\n"
                f"能力: {winner_proposal.capability}\n"
                f"理由: {winner_proposal.reasoning}\n"
                f"论据: {'; '.join(winner_proposal.arguments[:3])}"
            )
        else:
            explanation = "协商达成共识"

        return NegotiationResult(
            success=True,
            winner_id=proposal_agent_map.get(winner_id),
            winning_proposal=winner_proposal,
            all_scores=final_scores,
            rounds=len(self._rounds),
            explanation=explanation,
            consensus_type="hybrid",
        )

    def _resolve_unanimous(self) -> NegotiationResult:
        """一致同意模式：所有投票者都选择同一个提案。"""
        all_votes: List[VoteRecord] = []
        for rnd in self._rounds:
            all_votes.extend(rnd.votes)

        if not all_votes:
            return self._resolve_by_score()

        # 检查是否所有第一选择都指向同一提案
        first_choices = [
            v.proposal_id for v in all_votes
            if v.rank == ProposalRank.FIRST
        ]

        if first_choices and len(set(first_choices)) == 1:
            winner_id = first_choices[0]
            winner_proposal = self._proposals.get(winner_id)
            proposal_agent_map = {
                p.proposal_id: p.agent_id
                for p in self._proposals.values()
            }

            self._status = NegotiationStatus.RESOLVED
            explanation = (
                f"通过一致同意达成共识。\n"
                f"胜出: {proposal_agent_map.get(winner_id)} "
                f"(所有投票者一致选择)\n"
            )
            if winner_proposal:
                explanation += f"理由: {winner_proposal.reasoning}"

            return NegotiationResult(
                success=True,
                winner_id=proposal_agent_map.get(winner_id),
                winning_proposal=winner_proposal,
                rounds=len(self._rounds),
                explanation=explanation,
                consensus_type="unanimous",
            )

        # 未达成一致，退化为评分
        return self._resolve_by_score()

    def get_negotiation_summary(self) -> Dict[str, Any]:
        """获取协商摘要。"""
        return {
            "negotiation_id": self._negotiation_id,
            "type": self.negotiation_type.value,
            "topic": self.topic,
            "status": self._status.value,
            "rounds_completed": len(self._rounds),
            "max_rounds": self.max_rounds,
            "proposals_count": len(self._proposals),
            "total_votes": sum(
                len(r.votes) for r in self._rounds
            ),
            "elapsed_s": time.time() - self._start_time,
        }


# ---------------------------------------------------------------------------
# Convenience Functions
# ---------------------------------------------------------------------------

def quick_delegate(
    candidates: List[Dict[str, Any]],
    capability: str,
) -> NegotiationResult:
    """快速任务委派（无需手动创建提案）。

    Args:
        candidates: 候选 Agent 列表，每个包含:
            - agent_id: Agent ID
            - confidence: 信心分
            - quality_score: 质量分
            - reasoning: 理由
        capability: 需要的能力

    Returns:
        协商结果
    """
    session = NegotiationSession(
        negotiation_type=NegotiationType.TASK_DELEGATION,
        topic=f"委派任务: {capability}",
    )

    for candidate in candidates:
        proposal = AgentProposal(
            agent_id=candidate["agent_id"],
            capability=capability,
            confidence=candidate.get("confidence", 0.5),
            quality_score=candidate.get("quality_score", 0.5),
            reasoning=candidate.get("reasoning", ""),
            arguments=candidate.get("arguments", []),
            cost_score=candidate.get("cost_score", 0.5),
            speed_score=candidate.get("speed_score", 0.5),
        )
        session.add_proposal(proposal)

    return session.resolve(strategy="hybrid")


def resolve_capability_dispute(
    agent_scores: Dict[str, float],
    capability: str,
    context: Optional[Dict[str, Any]] = None,
) -> Tuple[Optional[str], float]:
    """解决能力争议（便捷函数）。

    Args:
        agent_scores: agent_id -> score 映射
        capability: 争议的能力
        context: 附加上下文

    Returns:
        (胜出 agent_id, 胜出得分)
    """
    if not agent_scores:
        return None, 0.0

    winner_id = max(agent_scores, key=agent_scores.get)
    winner_score = agent_scores[winner_id]
    return winner_id, winner_score
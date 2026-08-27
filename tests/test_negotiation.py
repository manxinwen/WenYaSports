"""Tests for Agent Negotiation Protocol."""

import pytest

from app.orchestrator.negotiation import (
    AgentProposal,
    NegotiationResult,
    NegotiationRound,
    NegotiationSession,
    NegotiationStatus,
    NegotiationType,
    ProposalRank,
    VoteRecord,
    quick_delegate,
    resolve_capability_dispute,
)


class TestAgentProposal:
    """Agent 提案测试。"""

    def test_composite_score_calculation(self):
        """综合评分计算。"""
        proposal = AgentProposal(
            agent_id="test_agent",
            capability="test_cap",
            confidence=0.9,
            quality_score=0.8,
            cost_score=0.3,  # 低成本 = 高效率
            speed_score=0.7,
        )
        # score = 0.9*0.3 + 0.8*0.3 + (1-0.3)*0.2 + 0.7*0.2
        #       = 0.27 + 0.24 + 0.14 + 0.14 = 0.79
        assert proposal.composite_score == pytest.approx(0.79, abs=0.01)

    def test_composite_score_range(self):
        """综合评分在合理范围内。"""
        proposal = AgentProposal(
            agent_id="test",
            capability="test",
            confidence=1.0,
            quality_score=1.0,
            cost_score=0.0,
            speed_score=1.0,
        )
        assert 0 <= proposal.composite_score <= 1

    def test_to_dict(self):
        """序列化。"""
        proposal = AgentProposal(
            agent_id="test",
            capability="cap",
            confidence=0.8,
        )
        data = proposal.to_dict()
        assert "agent_id" in data
        assert "composite_score" in data
        assert "proposal_id" in data


class TestNegotiationSession:
    """协商会话测试。"""

    def test_start_session(self):
        """创建协商会话。"""
        session = NegotiationSession(
            negotiation_type=NegotiationType.TASK_DELEGATION,
            topic="数据解析任务",
        )
        assert session.status == NegotiationStatus.PENDING
        assert session.current_round == 0

    def test_add_proposals(self):
        """添加提案。"""
        session = NegotiationSession(
            negotiation_type=NegotiationType.CAPABILITY_DISPUTE,
            topic="解析能力争议",
        )
        session.start_round()

        p1 = AgentProposal("agent_a", "parsing", confidence=0.9, quality_score=0.85)
        p2 = AgentProposal("agent_b", "parsing", confidence=0.7, quality_score=0.9)

        id1 = session.add_proposal(p1)
        id2 = session.add_proposal(p2)

        assert id1 != id2
        assert len(session.all_proposals) == 2

    def test_resolve_by_score(self):
        """基于评分解决。"""
        session = NegotiationSession(
            negotiation_type=NegotiationType.TASK_DELEGATION,
            topic="数据解析",
        )
        session.start_round()

        # 提案 A 综合分更高
        session.add_proposal(AgentProposal(
            "parser_agent", "parsing",
            confidence=0.9, quality_score=0.9,
            reasoning="直接解析专家",
            arguments=["支持多格式", "历史记录优秀"],
        ))
        session.add_proposal(AgentProposal(
            "feature_agent", "parsing",
            confidence=0.6, quality_score=0.5,
            reasoning="有一定解析能力",
        ))

        result = session.resolve(strategy="score_based")

        assert result.success is True
        assert result.winner_id == "parser_agent"
        assert result.winning_proposal is not None
        assert "parser_agent" in result.explanation

    def test_resolve_with_tight_scores(self):
        """分差太小时需要进一步协商。"""
        session = NegotiationSession(
            negotiation_type=NegotiationType.TASK_DELEGATION,
            topic="测试",
            min_score_diff=0.15,  # 较高的分差要求
        )
        session.start_round()

        # 两个非常接近的提案
        session.add_proposal(AgentProposal(
            "agent_a", "test",
            confidence=0.8, quality_score=0.8,
        ))
        session.add_proposal(AgentProposal(
            "agent_b", "test",
            confidence=0.78, quality_score=0.78,
        ))

        result = session.resolve(strategy="score_based")

        # 分差太小，可能需要进一步协商
        assert result.success is False
        assert "需要进一步协商" in result.explanation

    def test_resolve_by_voting(self):
        """基于投票解决。"""
        session = NegotiationSession(
            negotiation_type=NegotiationType.CONSENSUS_VOTING,
            topic="方案选择",
        )
        session.start_round()

        p1_id = session.add_proposal(AgentProposal(
            "plan_a", "planning",
            confidence=0.7, reasoning="方案 A",
        ))
        p2_id = session.add_proposal(AgentProposal(
            "plan_b", "planning",
            confidence=0.6, reasoning="方案 B",
        ))

        # 投票：agent_c 选 plan_a，agent_d 也选 plan_a
        session.cast_vote("agent_c", p1_id, ProposalRank.FIRST)
        session.cast_vote("agent_d", p1_id, ProposalRank.FIRST)
        session.cast_vote("agent_e", p2_id, ProposalRank.SECOND)

        result = session.resolve(strategy="vote_based")

        assert result.success is True
        assert result.winner_id == "plan_a"

    def test_resolve_hybrid(self):
        """混合策略解决。"""
        session = NegotiationSession(
            negotiation_type=NegotiationType.TASK_DELEGATION,
            topic="数据处理",
        )
        session.start_round()

        p1_id = session.add_proposal(AgentProposal(
            "specialist", "processing",
            confidence=0.9, quality_score=0.85,
            reasoning="领域专家",
        ))
        session.add_proposal(AgentProposal(
            "generalist", "processing",
            confidence=0.7, quality_score=0.7,
            reasoning="通用能力",
        ))

        # 投票支持 specialist
        session.cast_vote("voter_1", p1_id, ProposalRank.FIRST)
        session.cast_vote("voter_2", p1_id, ProposalRank.SECOND)

        result = session.resolve(strategy="hybrid")

        assert result.success is True
        assert result.winner_id == "specialist"
        assert "混合策略" in result.explanation

    def test_resolve_unanimous(self):
        """一致同意模式。"""
        session = NegotiationSession(
            negotiation_type=NegotiationType.CONSENSUS_VOTING,
            topic="决策",
        )
        session.start_round()

        p1_id = session.add_proposal(AgentProposal(
            "option_a", "decision",
            confidence=0.8,
        ))
        session.add_proposal(AgentProposal(
            "option_b", "decision",
            confidence=0.5,
        ))

        # 所有人一致选择 option_a
        session.cast_vote("voter_1", p1_id, ProposalRank.FIRST)
        session.cast_vote("voter_2", p1_id, ProposalRank.FIRST)
        session.cast_vote("voter_3", p1_id, ProposalRank.FIRST)

        result = session.resolve(strategy="unanimous")

        assert result.success is True
        assert result.winner_id == "option_a"
        assert "一致同意" in result.explanation

    def test_no_proposals_fails(self):
        """无提案时协商失败。"""
        session = NegotiationSession(
            negotiation_type=NegotiationType.TASK_DELEGATION,
            topic="空协商",
        )
        session.start_round()

        result = session.resolve()

        assert result.success is False
        assert "无 Agent 提案" in result.explanation

    def test_voter_authority(self):
        """投票者权威度影响权重。"""
        session = NegotiationSession(
            negotiation_type=NegotiationType.CONSENSUS_VOTING,
            topic="加权投票",
        )
        session.start_round()

        p1_id = session.add_proposal(AgentProposal("a", "test"))
        p2_id = session.add_proposal(AgentProposal("b", "test"))

        # 设置权威度：voter_high 权重 1.0，voter_low 权重 0.2
        session.set_voter_authority("voter_high", 1.0)
        session.set_voter_authority("voter_low", 0.2)

        # voter_low 投 p1，voter_high 投 p2
        session.cast_vote("voter_low", p1_id, ProposalRank.FIRST)  # weight=0.2
        session.cast_vote("voter_high", p2_id, ProposalRank.FIRST)  # weight=1.0

        result = session.resolve(strategy="vote_based")

        # voter_high 权重更高，p2 应该胜出
        assert result.winner_id == "b"

    def test_negotiation_summary(self):
        """协商摘要。"""
        session = NegotiationSession(
            negotiation_type=NegotiationType.TASK_DELEGATION,
            topic="摘要测试",
        )
        session.start_round()
        session.add_proposal(AgentProposal("a", "test"))
        session.add_proposal(AgentProposal("b", "test"))

        summary = session.get_negotiation_summary()

        assert summary["type"] == "task_delegation"
        assert summary["proposals_count"] == 2
        assert summary["rounds_completed"] == 1


class TestQuickFunctions:
    """便捷函数测试。"""

    def test_quick_delegate(self):
        """快速任务委派。"""
        candidates = [
            {
                "agent_id": "parser",
                "confidence": 0.9,
                "quality_score": 0.85,
                "reasoning": "专业解析",
            },
            {
                "agent_id": "feature",
                "confidence": 0.6,
                "quality_score": 0.7,
                "reasoning": "附带解析能力",
            },
        ]

        result = quick_delegate(candidates, "data_parsing")

        assert result.success is True
        assert result.winner_id == "parser"

    def test_resolve_capability_dispute(self):
        """解决能力争议。"""
        scores = {
            "agent_a": 0.85,
            "agent_b": 0.72,
            "agent_c": 0.91,
        }

        winner, score = resolve_capability_dispute(scores, "parsing")

        assert winner == "agent_c"
        assert score == 0.91

    def test_resolve_capability_dispute_empty(self):
        """空输入处理。"""
        winner, score = resolve_capability_dispute({}, "test")
        assert winner is None
        assert score == 0.0
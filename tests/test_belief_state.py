"""Tests for BeliefState, UtilityFunction, and GoalMonitor."""

import pytest
import time

from app.orchestrator.belief_state import (
    Belief,
    BeliefState,
    BeliefStateSnapshot,
    Hypothesis,
    InformationNeed,
    UtilityFunction,
    ActionOption,
    GoalMonitor,
)


class TestBeliefState:
    """BeliefState 测试。"""

    def test_observe_and_retrieve(self):
        """添加观察并检索。"""
        state = BeliefState(user_id="test")

        belief = state.observe("数据解析成功", confidence=0.9)
        assert belief.fact == "数据解析成功"
        assert belief.confidence == 0.9

        # 检索
        assert state.is_confident("数据解析成功", threshold=0.7)
        assert state.get_confidence("数据解析成功") == 0.9

    def test_observe_updates_existing(self):
        """更新已存在的信念。"""
        state = BeliefState()

        state.observe("数据解析成功", confidence=0.5)
        state.observe("数据解析成功", confidence=0.9)

        # 贝叶斯更新后应在中间值
        conf = state.get_confidence("数据解析成功")
        assert 0.5 <= conf <= 0.9

    def test_is_confident_threshold(self):
        """置信度阈值判断。"""
        state = BeliefState()

        state.observe("事实A", confidence=0.5)
        assert state.is_confident("事实A", threshold=0.3)
        assert not state.is_confident("事实A", threshold=0.8)

    def test_unknown_fact_returns_zero(self):
        """未知事实返回 0 置信度。"""
        state = BeliefState()
        assert state.get_confidence("不存在的事实") == 0.0
        assert not state.is_confident("不存在的事实")

    def test_hypothesis_management(self):
        """假设管理。"""
        state = BeliefState()

        hyp = state.propose_hypothesis("用户心率偏高", prior_probability=0.5)
        assert hyp.posterior_probability == 0.5

        # 添加支持
        state.support_hypothesis("用户心率偏高")
        state.support_hypothesis("用户心率偏高")
        # 后验概率应提高
        assert hyp.posterior_probability > 0.5

        # 添加反证
        state.contradict_hypothesis("用户心率偏高")
        assert hyp.posterior_probability < 1.0

    def test_active_hypotheses(self):
        """获取活跃假设。"""
        state = BeliefState()

        state.propose_hypothesis("假设A", prior_probability=0.5)
        state.propose_hypothesis("假设B", prior_probability=0.1)

        active = state.get_active_hypotheses(min_probability=0.3)
        assert len(active) >= 1

    def test_information_needs(self):
        """信息需求管理。"""
        state = BeliefState()

        state.add_information_need("用户年龄", priority=0.8)
        state.add_information_need("运动历史", priority=0.5)

        top = state.get_top_needs(n=1)
        assert len(top) == 1
        assert top[0].question == "用户年龄"

        state.resolve_need("用户年龄")
        remaining = state.get_top_needs()
        assert all(n.question != "用户年龄" for n in remaining)

    def test_goal_coverage(self):
        """目标覆盖率。"""
        state = BeliefState()

        state.set_goal_coverage("解析数据", 1.0)
        state.set_goal_coverage("分析特征", 0.5)

        coverage = state.get_overall_coverage()
        assert coverage == 0.75

        assert not state.is_goal_satisfied(threshold=0.9)
        assert state.is_goal_satisfied(threshold=0.7)

    def test_overall_confidence(self):
        """整体置信度。"""
        state = BeliefState()

        # 空状态
        assert state.get_overall_confidence() == 0.0

        state.observe("A", confidence=0.9)
        state.observe("B", confidence=0.3)

        # 平均置信度
        conf = state.get_overall_confidence()
        assert 0.3 <= conf <= 0.9

    def test_snapshot(self):
        """快照生成。"""
        state = BeliefState()
        state.observe("事实A", confidence=0.8)
        state.propose_hypothesis("假设X")

        snapshot = state.get_snapshot()
        assert snapshot.total_beliefs == 1
        assert snapshot.hypotheses_count == 1
        assert snapshot.overall_confidence > 0

    def test_to_dict(self):
        """序列化。"""
        state = BeliefState()
        state.observe("事实A", confidence=0.9)

        data = state.to_dict()
        assert "beliefs" in data
        assert data["beliefs"]["事实A"]["confidence"] == 0.9


class TestUtilityFunction:
    """UtilityFunction 测试。"""

    def test_compute_utility(self):
        """效用计算。"""
        uf = UtilityFunction()

        option = ActionOption(
            action="parse_file",
            description="解析文件",
            expected_success_rate=0.9,
            expected_quality_impact=0.3,
            cost=1.0,
        )

        utility = uf.compute_utility(option)
        assert utility > 0.0

    def test_select_best(self):
        """选择最优行动。"""
        uf = UtilityFunction()

        options = [
            ActionOption("A", "高成功率", 0.9, 0.2, 1.0),
            ActionOption("B", "低成功率", 0.3, 0.1, 0.1),
        ]

        best, best_utility, all_scored = uf.select_best(options)
        assert best.action == "A"
        assert best_utility > 0

    def test_empty_options_raises(self):
        """空选项应抛异常。"""
        uf = UtilityFunction()
        with pytest.raises(ValueError):
            uf.select_best([])

    def test_utility_with_beliefs(self):
        """带信念状态的效用计算。"""
        uf = UtilityFunction()
        beliefs = BeliefState()

        option = ActionOption(
            action="urgent_task",
            description="紧急任务",
            urgency=0.9,
        )

        utility_no_beliefs = uf.compute_utility(option)
        utility_with_beliefs = uf.compute_utility(option, beliefs)

        # 有信念状态时应加入紧迫性奖励
        assert utility_with_beliefs >= utility_no_beliefs

    def test_get_stats(self):
        """统计信息。"""
        uf = UtilityFunction()
        stats = uf.get_stats()
        assert "weights" in stats


class TestGoalMonitor:
    """GoalMonitor 测试。"""

    def test_completion_all_passed(self):
        """所有检查通过。"""
        monitor = GoalMonitor(min_coverage=0.5, min_confidence=0.5)
        beliefs = BeliefState()
        beliefs.observe("事实", confidence=0.9)
        beliefs.set_goal_coverage("任务", 1.0)

        is_done, reason, checks = monitor.check_completion(
            beliefs=beliefs,
            quality_score=80.0,
        )

        assert is_done
        assert "完成" in reason

    def test_completion_fails_coverage(self):
        """覆盖率不足。"""
        monitor = GoalMonitor(min_coverage=0.9)
        beliefs = BeliefState()
        beliefs.set_goal_coverage("任务", 0.5)

        is_done, reason, checks = monitor.check_completion(
            beliefs=beliefs,
            quality_score=80.0,
        )

        assert not is_done
        assert "覆盖率不足" in reason

    def test_completion_fails_quality(self):
        """质量不足。"""
        monitor = GoalMonitor(min_quality_score=90.0)

        is_done, reason, checks = monitor.check_completion(
            beliefs=None,
            quality_score=50.0,
        )

        assert not is_done
        assert "质量分不足" in reason

    def test_abandon_decision(self):
        """放弃判断。"""
        monitor = GoalMonitor()

        assert not monitor.should_abandon(2, max_consecutive_failures=3)
        assert monitor.should_abandon(3, max_consecutive_failures=3)
        assert monitor.should_abandon(5, max_consecutive_failures=3)

    def test_additional_checks(self):
        """额外检查项。"""
        monitor = GoalMonitor()

        is_done, reason, checks = monitor.check_completion(
            beliefs=None,
            quality_score=80.0,
            additional_checks={"api_available": True, "user_approved": False},
        )

        assert not is_done
        assert "user_approved" in reason

    def test_get_stats(self):
        """统计信息。"""
        monitor = GoalMonitor()

        monitor.check_completion(beliefs=None, quality_score=80.0)
        monitor.check_completion(beliefs=None, quality_score=50.0)

        stats = monitor.get_stats()
        assert "total_checks" in stats
        assert stats["total_checks"] == 2

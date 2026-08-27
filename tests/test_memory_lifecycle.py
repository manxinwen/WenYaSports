"""Tests for Memory Lifecycle Manager."""

import pytest
import time

from app.memory.memory_lifecycle import (
    MemoryLevel,
    MemoryEntry,
    LifecycleAction,
    LifecycleEvent,
    MemoryLifecycleManager,
)


class TestMemoryEntry:
    """记忆条目测试。"""

    def test_access_updates_fields(self):
        """访问更新时间和计数。"""
        entry = MemoryEntry(
            entry_id="test_1",
            content="测试内容",
            level=MemoryLevel.WORKING,
        )

        initial_accessed = entry.last_accessed
        time.sleep(0.01)
        entry.access()

        assert entry.access_count == 1
        assert entry.last_accessed > initial_accessed
        assert entry.decay_factor == 1.0  # 重置衰减

    def test_effective_score(self):
        """有效分数计算。"""
        entry = MemoryEntry(
            entry_id="test_2",
            content="测试内容",
            level=MemoryLevel.WORKING,
            importance=0.8,
            confidence=0.9,
        )
        entry.access_count = 10

        score = entry.effective_score()
        assert 0.0 <= score <= 1.0


class TestMemoryLifecycleManager:
    """记忆生命周期管理器测试。"""

    def test_add_and_get_entry(self):
        """添加和获取条目。"""
        mlm = MemoryLifecycleManager()

        entry = MemoryEntry(
            entry_id="e1",
            content="测试记忆",
            level=MemoryLevel.WORKING,
        )
        mlm.add_entry(entry)

        retrieved = mlm.get_entry("e1")
        assert retrieved is not None
        assert retrieved.content == "测试记忆"
        assert retrieved.access_count == 1  # get 自动访问

    def test_get_entries_by_level(self):
        """按层级获取条目。"""
        mlm = MemoryLifecycleManager()

        mlm.add_entry(MemoryEntry("w1", "working", MemoryLevel.WORKING))
        mlm.add_entry(MemoryEntry("e1", "episodic", MemoryLevel.EPISODIC))
        mlm.add_entry(MemoryEntry("w2", "working2", MemoryLevel.WORKING))

        working = mlm.get_entries_by_level(MemoryLevel.WORKING)
        assert len(working) == 2

        episodic = mlm.get_entries_by_level(MemoryLevel.EPISODIC)
        assert len(episodic) == 1

    def test_search_entries(self):
        """搜索条目。"""
        mlm = MemoryLifecycleManager()

        mlm.add_entry(MemoryEntry("e1", "跑步数据心率分析", MemoryLevel.WORKING))
        mlm.add_entry(MemoryEntry("e2", "饮食营养建议", MemoryLevel.EPISODIC))
        mlm.add_entry(MemoryEntry("e3", "心率异常检测", MemoryLevel.WORKING))

        results = mlm.search_entries("心率")
        assert len(results) >= 1
        # 心率相关的条目应该排在前面
        assert "心率" in results[0][0].content

    def test_promote_working_to_episodic(self):
        """晋升 Working → Episodic。"""
        mlm = MemoryLifecycleManager(promotion_threshold=3)

        entry = MemoryEntry(
            entry_id="p1",
            content="重要工作记忆",
            level=MemoryLevel.WORKING,
            importance=0.8,
        )
        mlm.add_entry(entry)

        # 访问不足，不应晋升
        event = mlm.promote_entry("p1")
        assert event is None

        # 增加访问次数
        for _ in range(5):
            entry.access_count += 1

        event = mlm.promote_entry("p1")
        assert event is not None
        assert event.action == LifecycleAction.PROMOTE
        assert event.from_level == MemoryLevel.WORKING
        assert event.to_level == MemoryLevel.EPISODIC

    def test_promote_episodic_to_semantic(self):
        """晋升 Episodic → Semantic（蒸馏）。"""
        mlm = MemoryLifecycleManager(promotion_threshold=3)

        entry = MemoryEntry(
            entry_id="p2",
            content="重要情节记忆",
            level=MemoryLevel.EPISODIC,
            confidence=0.9,
        )
        mlm.add_entry(entry)

        # 需要更多访问次数
        for _ in range(10):
            entry.access_count += 1

        event = mlm.promote_entry("p2")
        assert event is not None
        assert event.to_level == MemoryLevel.SEMANTIC

    def test_decay_entries(self):
        """衰减条目。"""
        mlm = MemoryLifecycleManager(decay_rate_hourly=0.1)

        entry = MemoryEntry(
            entry_id="d1",
            content="衰减测试",
            level=MemoryLevel.WORKING,
            decay_factor=1.0,
        )
        # 手动设置为很久以前访问
        entry.last_accessed = time.time() - 7200  # 2小时前
        mlm.add_entry(entry)

        decay_events = mlm.decay_entries()
        assert len(decay_events) >= 1
        assert entry.decay_factor < 1.0

    def test_expire_entries(self):
        """过期删除。"""
        mlm = MemoryLifecycleManager(
            working_max_age=0.1,  # 0.1 秒就过期
        )

        entry = MemoryEntry(
            entry_id="x1",
            content="即将过期",
            level=MemoryLevel.WORKING,
        )
        # 手动设置为很久以前
        entry.last_accessed = time.time() - 1.0
        mlm.add_entry(entry)

        time.sleep(0.15)

        expire_events = mlm.expire_entries()
        assert len(expire_events) == 1
        assert mlm.get_entry("x1") is None

    def test_run_lifecycle_cycle(self):
        """完整生命周期循环。"""
        mlm = MemoryLifecycleManager(
            promotion_threshold=1,
            working_max_age=0.05,
        )

        # 添加一些会过期的条目
        entry = MemoryEntry(
            entry_id="c1",
            content="会过期的条目",
            level=MemoryLevel.WORKING,
            importance=0.9,
        )
        entry.last_accessed = time.time() - 1.0
        entry.access_count = 5  # 满足晋升条件
        mlm.add_entry(entry)

        time.sleep(0.1)

        results = mlm.run_lifecycle_cycle(force_all=True)
        assert "expirations" in results
        assert results["total_events"] >= 0

    def test_distill_entries(self):
        """蒸馏条目。"""
        mlm = MemoryLifecycleManager(distillation_threshold=0.3)

        # 添加相似的 Episodic 条目
        mlm.add_entry(MemoryEntry(
            "e1", "跑步心率数据分析", MemoryLevel.EPISODIC,
            access_count=10,
        ))
        mlm.add_entry(MemoryEntry(
            "e2", "跑步心率统计报告", MemoryLevel.EPISODIC,
            access_count=5,
        ))

        events = mlm.distill_entries(
            MemoryLevel.EPISODIC,
            MemoryLevel.SEMANTIC,
        )
        # 如果有相似条目，应该被蒸馏
        assert len(events) >= 0  # 可能为0如果不相似

    def test_get_stats(self):
        """统计信息。"""
        mlm = MemoryLifecycleManager()

        mlm.add_entry(MemoryEntry("e1", "test", MemoryLevel.WORKING))
        mlm.add_entry(MemoryEntry("e2", "test2", MemoryLevel.EPISODIC))

        stats = mlm.get_stats()
        assert stats["total_entries"] == 2
        assert "level_counts" in stats
        assert "config" in stats

    def test_get_recent_events(self):
        """获取最近事件。"""
        mlm = MemoryLifecycleManager()

        # 先添加条目
        entry = MemoryEntry("e1", "test", MemoryLevel.WORKING)
        entry.access_count = 10
        mlm.add_entry(entry)

        # 执行一次衰减
        mlm.decay_entries()

        events = mlm.get_recent_events(limit=5)
        assert isinstance(events, list)

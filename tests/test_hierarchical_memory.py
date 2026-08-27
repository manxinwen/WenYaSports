"""Hierarchical Memory System Tests."""

import json
import os
import time

import pytest

from app.memory import (
    HierarchicalMemory,
    WorkingMemory,
    EpisodicMemory,
    SemanticMemory,
)


# ---------------------------------------------------------------------------
# WorkingMemory Tests
# ---------------------------------------------------------------------------

class TestWorkingMemory:
    """工作记忆测试。"""

    def test_store_and_retrieve_recent(self):
        wm = WorkingMemory(max_entries=5)
        wm.store("消息1")
        wm.store("消息2")
        wm.store("消息3")

        results = wm.get_recent(n=2)
        assert len(results) == 2
        assert results[0]["content"] == "消息3"
        assert results[1]["content"] == "消息2"

    def test_retrieve_with_query(self):
        wm = WorkingMemory()
        wm.store("今天我跑了5公里，感觉很棒")
        wm.store("昨天做了力量训练")
        wm.store("跑步配速控制在每分钟6分钟")

        results = wm.retrieve(query="跑步", top_k=2)
        assert len(results) > 0
        assert any("跑步" in r["content"] for r in results)

    def test_max_entries_eviction(self):
        wm = WorkingMemory(max_entries=3)
        wm.store("条目1")
        wm.store("条目2")
        wm.store("条目3")
        wm.store("条目4")

        assert len(wm) == 3
        results = wm.get_recent(n=3)
        contents = [r["content"] for r in results]
        assert "条目4" in contents
        assert "条目1" not in contents

    def test_ttl_expiry(self):
        wm = WorkingMemory(max_entries=10, ttl_seconds=0.1)
        wm.store("短暂消息")
        assert len(wm) == 1

        time.sleep(0.15)
        wm._cleanup()
        assert len(wm) == 0

    def test_export_import(self):
        wm = WorkingMemory(max_entries=10)
        wm.store("导出测试1", metadata={"key": "val1"})
        wm.store("导出测试2", metadata={"key": "val2"})

        data = wm.export()
        wm2 = WorkingMemory()
        wm2.import_(data)

        assert len(wm2) == 2
        results = wm2.get_recent(n=2)
        assert results[0]["content"] == "导出测试2"

    def test_clear(self):
        wm = WorkingMemory()
        wm.store("消息")
        assert len(wm) == 1
        wm.clear()
        assert len(wm) == 0

    def test_metadata_preserved(self):
        wm = WorkingMemory()
        wm.store("测试", metadata={"user": "u1", "session": "s1"})
        results = wm.get_recent(n=1)
        assert results[0]["metadata"]["user"] == "u1"
        assert results[0]["metadata"]["session"] == "s1"


# ---------------------------------------------------------------------------
# EpisodicMemory Tests
# ---------------------------------------------------------------------------

class TestEpisodicMemory:
    """情节记忆测试。"""

    def test_store_and_retrieve_basic(self):
        em = EpisodicMemory()
        em.store(
            content="用户问了跑步配速问题",
            topic="跑步",
            agents=["coordinator", "recommender"],
            outcome="成功给出建议",
        )

        results = em.retrieve(query="跑步", top_k=3)
        assert len(results) > 0
        assert results[0]["topic"] == "跑步"

    def test_filter_by_topic(self):
        em = EpisodicMemory()
        em.store("内容A", topic="跑步")
        em.store("内容B", topic="骑行")
        em.store("内容C", topic="跑步")

        results = em.retrieve(topic="跑步")
        assert len(results) == 2

    def test_filter_by_agent(self):
        em = EpisodicMemory()
        em.store("内容A", agents=["parser", "coordinator"])
        em.store("内容B", agents=["recommender"])
        em.store("内容C", agents=["parser"])

        results = em.retrieve(agent="parser")
        assert len(results) == 2

    def test_filter_by_outcome(self):
        em = EpisodicMemory()
        em.store("内容A", outcome="成功")
        em.store("内容B", outcome="失败")
        em.store("内容C", outcome="成功")

        results = em.retrieve(outcome="成功")
        assert len(results) == 2

    def test_filter_by_metadata(self):
        em = EpisodicMemory()
        em.store("内容A", metadata={"user_id": "u1", "priority": "high"})
        em.store("内容B", metadata={"user_id": "u2", "priority": "low"})

        results = em.retrieve(metadata_filter={"user_id": "u1"})
        assert len(results) == 1
        assert results[0]["content"] == "内容A"

    def test_text_retrieval_scoring(self):
        em = EpisodicMemory()
        em.store("跑步训练应该循序渐进，避免过度训练", topic="跑步")
        em.store("骑行训练需要注意姿势和 gear 选择", topic="骑行")
        em.store("游泳时要注意呼吸节奏和身体流线", topic="游泳")

        results = em.retrieve(query="跑步训练", top_k=2)
        assert len(results) > 0
        assert "跑步" in results[0]["content"]

    def test_export_import(self):
        em = EpisodicMemory()
        em.store("测试内容", topic="测试", agents=["agent1"])

        data = em.export()
        em2 = EpisodicMemory()
        em2.import_(data)

        assert len(em2) == 1
        results = em2.retrieve(topic="测试")
        assert results[0]["content"] == "测试内容"

    def test_max_episodes_eviction(self):
        em = EpisodicMemory(max_episodes=3)
        for i in range(5):
            em.store(f"情节{i}", topic=f"topic{i}")

        assert len(em) == 3
        results = em.retrieve(topic="topic4")
        assert len(results) == 1


# ---------------------------------------------------------------------------
# SemanticMemory Tests
# ---------------------------------------------------------------------------

class TestSemanticMemory:
    """语义记忆测试。"""

    def test_store_and_retrieve_basic(self):
        sm = SemanticMemory()
        sm.store(
            content="跑步训练应遵循循序渐进原则",
            source="running_guide.md",
            domain="跑步",
            tags=["训练", "原则"],
        )

        results = sm.retrieve(query="跑步训练", top_k=3)
        assert len(results) > 0

    def test_filter_by_domain(self):
        sm = SemanticMemory()
        sm.store("跑步知识", domain="跑步")
        sm.store("骑行知识", domain="骑行")
        sm.store("游泳知识", domain="游泳")

        results = sm.retrieve(query="知识", domain="跑步")
        assert len(results) == 1
        assert results[0]["domain"] == "跑步"

    def test_filter_by_tags(self):
        sm = SemanticMemory()
        sm.store("内容A", tags=["训练", "入门"])
        sm.store("内容B", tags=["营养", "饮食"])
        sm.store("内容C", tags=["训练", "进阶"])

        results = sm.retrieve(query="内容", tags=["训练"])
        assert len(results) == 2

    def test_text_retrieval_scoring(self):
        sm = SemanticMemory()
        sm.store(
            "间歇跑能有效提升最大摄氧量和心肺功能",
            domain="跑步",
            tags=["间歇", "体能"],
        )
        sm.store(
            "恢复日应保持低强度活动，帮助身体修复",
            domain="跑步",
            tags=["恢复", "低强度"],
        )
        sm.store(
            "力量训练可以增强肌肉和骨骼密度",
            domain="力量",
            tags=["力量", "肌肉"],
        )

        results = sm.retrieve(query="间歇跑 体能提升", top_k=2)
        assert len(results) > 0
        assert "间歇" in results[0]["content"]

    def test_metadata_filter(self):
        sm = SemanticMemory()
        sm.store("知识A", metadata={"version": 1, "verified": True})
        sm.store("知识B", metadata={"version": 2, "verified": False})

        results = sm.retrieve(query="知识", metadata_filter={"verified": True})
        assert len(results) == 1

    def test_export_import(self):
        sm = SemanticMemory()
        sm.store("测试知识", domain="测试", tags=["tag1"])

        data = sm.export()
        sm2 = SemanticMemory()
        sm2.import_(data)

        assert len(sm2) == 1
        results = sm2.retrieve(query="测试")
        assert len(results) > 0

    def test_empty_query_returns_all(self):
        sm = SemanticMemory()
        sm.store("知识1")
        sm.store("知识2")
        sm.store("知识3")

        results = sm.retrieve(query="")
        assert len(results) == 3


# ---------------------------------------------------------------------------
# HierarchicalMemory Orchestrator Tests
# ---------------------------------------------------------------------------

class TestHierarchicalMemory:
    """分级记忆协调器测试。"""

    def test_auto_route_to_semantic(self):
        hm = HierarchicalMemory()
        result = hm.store(
            "跑者应该每周逐渐增加跑量",
            domain="跑步",
            tags=["训练建议"],
        )
        assert result["level"] == "semantic"

    def test_auto_route_to_episodic(self):
        hm = HierarchicalMemory()
        result = hm.store(
            "用户进行了跑步配速咨询",
            topic="跑步",
            agents=["coordinator"],
        )
        assert result["level"] == "episodic"

    def test_auto_route_to_working(self):
        hm = HierarchicalMemory()
        result = hm.store("这是一条普通的会话消息")
        assert result["level"] == "working"

    def test_explicit_levels(self):
        hm = HierarchicalMemory()
        hm.store("工作记忆", level="working")
        hm.store("情节记忆", level="episodic", topic="测试")
        hm.store("语义记忆", level="semantic", domain="测试")

        assert len(hm.working) == 1
        assert len(hm.episodic) == 1
        assert len(hm.semantic) == 1

    def test_cross_layer_retrieve(self):
        hm = HierarchicalMemory()
        hm.store("跑步是一种有氧运动", level="semantic", domain="跑步")
        hm.store("用户问了跑步问题", level="episodic", topic="跑步")
        hm.store("当前在讨论跑步训练", level="working")

        results = hm.retrieve(query="跑步", top_k=5)
        assert len(results) > 0

    def test_single_layer_retrieve(self):
        hm = HierarchicalMemory()
        hm.store("工作记忆跑步", level="working")
        hm.store("情节记忆跑步", level="episodic", topic="跑步")
        hm.store("语义记忆跑步", level="semantic", domain="跑步")

        semantic_results = hm.retrieve(query="跑步", level="semantic")
        assert len(semantic_results) >= 1
        assert semantic_results[0]["level"] == "semantic"

    def test_export_to_file_and_import(self, tmp_path):
        filepath = str(tmp_path / "memory_backup.json")
        hm = HierarchicalMemory()
        hm.store("工作消息", level="working")
        hm.store("情节消息", level="episodic", topic="测试")
        hm.store("语义消息", level="semantic", domain="测试")

        hm.export_to_file(filepath)
        assert os.path.exists(filepath)

        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        hm2 = HierarchicalMemory()
        hm2.import_(data)
        assert len(hm2.working) == 1
        assert len(hm2.episodic) == 1
        assert len(hm2.semantic) == 1

    def test_get_stats(self):
        hm = HierarchicalMemory()
        hm.store("w", level="working")
        hm.store("e", level="episodic", topic="t")
        hm.store("s", level="semantic", domain="d")

        stats = hm.get_stats()
        assert stats["working_count"] == 1
        assert stats["episodic_count"] == 1
        assert stats["semantic_count"] == 1

    def test_clear_specific_level(self):
        hm = HierarchicalMemory()
        hm.store("w1", level="working")
        hm.store("w2", level="working")
        hm.store("e1", level="episodic", topic="t")

        hm.clear(level="working")
        assert len(hm.working) == 0
        assert len(hm.episodic) == 1

    def test_clear_all(self):
        hm = HierarchicalMemory()
        hm.store("w", level="working")
        hm.store("e", level="episodic", topic="t")
        hm.store("s", level="semantic", domain="d")

        hm.clear()
        assert len(hm.working) == 0
        assert len(hm.episodic) == 0
        assert len(hm.semantic) == 0

    def test_invalid_level_raises(self):
        hm = HierarchicalMemory()
        with pytest.raises(ValueError):
            hm.store("test", level="invalid_level")

    def test_invalid_retrieve_level_raises(self):
        hm = HierarchicalMemory()
        with pytest.raises(ValueError):
            hm.retrieve("test", level="invalid_level")
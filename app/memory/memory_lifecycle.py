"""Memory Lifecycle Manager: 记忆生命周期管理。

让记忆系统具备「新陈代谢」能力：
- 自动晋升：Working 记忆中频繁访问的条目自动晋升到 Episodic
- 自动蒸馏：Episodic 记忆定期合并相似条目，蒸馏为 Semantic 知识
- 自动衰减：长期未访问的记忆条目逐渐衰减直至消失

设计借鉴认知科学的「记忆巩固」理论：
- Working Memory → Episodic Memory: 通过反复访问实现「练习效应」
- Episodic Memory → Semantic Memory: 通过抽象概括实现「知识提炼」
- 记忆衰减：模拟「遗忘曲线」，越久未访问越难检索
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data Structures
# ---------------------------------------------------------------------------

class MemoryLevel(Enum):
    """记忆层级。"""
    WORKING = "working"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"


class LifecycleAction(Enum):
    """生命周期操作。"""
    PROMOTE = "promote"           # 晋升
    DISTILL = "distill"           # 蒸馏
    DECAY = "decay"               # 衰减
    EXPIRE = "expire"             # 过期删除
    CONSOLIDATE = "consolidate"   # 整合


@dataclass
class MemoryEntry:
    """统一的记忆条目。"""
    entry_id: str
    content: str
    level: MemoryLevel
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)
    access_count: int = 0
    importance: float = 0.5       # 重要性 [0, 1]
    confidence: float = 1.0        # 置信度 [0, 1]
    decay_factor: float = 1.0      # 当前衰减因子
    tags: List[str] = field(default_factory=list)
    source_entry_id: Optional[str] = None  # 来源条目（蒸馏时记录）

    def access(self) -> None:
        """访问条目，更新时间和计数。"""
        self.last_accessed = time.time()
        self.access_count += 1
        # 访问重置衰减
        self.decay_factor = min(1.0, self.decay_factor + 0.1)

    def effective_score(self) -> float:
        """计算有效分数（用于检索排序）。"""
        recency = 1.0 / max(time.time() - self.last_accessed, 1.0)
        frequency = min(self.access_count / 10.0, 1.0)
        return (self.importance * 0.4
                + self.confidence * 0.3
                + frequency * 0.2
                + recency * 0.1) * self.decay_factor


@dataclass
class LifecycleEvent:
    """生命周期事件记录。"""
    timestamp: float
    action: LifecycleAction
    entry_id: str
    from_level: Optional[MemoryLevel] = None
    to_level: Optional[MemoryLevel] = None
    details: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Memory Lifecycle Manager
# ---------------------------------------------------------------------------

class MemoryLifecycleManager:
    """记忆生命周期管理器。

    核心职责：
    1. 记忆晋升：Working → Episodic（基于访问频率）
    2. 记忆蒸馏：Episodic → Semantic（基于内容相似度合并）
    3. 记忆衰减：基于时间和访问模式的自动衰减
    4. 记忆过期：超过最大保留时间的条目自动清理

    Usage:
        mlm = MemoryLifecycleManager(
            promotion_threshold=5,  # 访问5次后晋升
            decay_rate=0.95,        # 每周衰减5%
        )

        # 添加记忆
        mlm.add_entry(MemoryEntry(...))

        # 执行生命周期检查
        events = mlm.run_lifecycle_cycle()
    """

    def __init__(
        self,
        working_max_age: float = 3600.0,       # Working 最大保留时间（秒）
        episodic_max_age: float = 604800.0,   # Episodic 最大保留时间（7天）
        semantic_max_age: float = 2592000.0,  # Semantic 最大保留时间（30天）
        promotion_threshold: int = 5,          # 晋升所需访问次数
        promotion_min_importance: float = 0.3,  # 晋升最低重要性
        distillation_threshold: float = 0.7,  # 蒸馏相似度阈值
        decay_rate_hourly: float = 0.01,      # 每小时衰减率
        min_decay_factor: float = 0.1,        # 最小衰减因子
        auto_consolidate: bool = True,        # 自动整合开关
    ):
        """初始化记忆生命周期管理器。

        Args:
            working_max_age: Working 记忆最大保留时间
            episodic_max_age: Episodic 记忆最大保留时间
            semantic_max_age: Semantic 记忆最大保留时间
            promotion_threshold: 晋升所需访问次数
            promotion_min_importance: 晋升最低重要性
            distillation_threshold: 蒸馏相似度阈值
            decay_rate_hourly: 每小时衰减率
            min_decay_factor: 最小衰减因子
            auto_consolidate: 是否自动整合
        """
        self.working_max_age = working_max_age
        self.episodic_max_age = episodic_max_age
        self.semantic_max_age = semantic_max_age
        self.promotion_threshold = promotion_threshold
        self.promotion_min_importance = promotion_min_importance
        self.distillation_threshold = distillation_threshold
        self.decay_rate_hourly = decay_rate_hourly
        self.min_decay_factor = min_decay_factor
        self.auto_consolidate = auto_consolidate

        # 记忆存储
        self._entries: Dict[str, MemoryEntry] = {}
        self._events: List[LifecycleEvent] = []

        # 统计
        self._promotions_count = 0
        self._distillations_count = 0
        self._decays_count = 0
        self._expirations_count = 0

    # ------------------------------------------------------------------
    # 条目管理
    # ------------------------------------------------------------------

    def add_entry(self, entry: MemoryEntry) -> str:
        """添加记忆条目。

        Args:
            entry: 记忆条目

        Returns:
            条目 ID
        """
        if not entry.entry_id:
            entry.entry_id = f"mem_{time.time_ns()}"

        self._entries[entry.entry_id] = entry
        return entry.entry_id

    def get_entry(self, entry_id: str) -> Optional[MemoryEntry]:
        """获取记忆条目（自动更新访问信息）。"""
        entry = self._entries.get(entry_id)
        if entry:
            entry.access()
        return entry

    def get_entries_by_level(self, level: MemoryLevel) -> List[MemoryEntry]:
        """获取指定层级的所有条目。"""
        return [e for e in self._entries.values() if e.level == level]

    def get_all_entries(self) -> List[MemoryEntry]:
        """获取所有条目。"""
        return list(self._entries.values())

    def remove_entry(self, entry_id: str) -> bool:
        """删除条目。"""
        if entry_id in self._entries:
            del self._entries[entry_id]
            return True
        return False

    def search_entries(
        self,
        query: str,
        level: Optional[MemoryLevel] = None,
        top_k: int = 5,
    ) -> List[Tuple[MemoryEntry, float]]:
        """搜索相关条目。

        Args:
            query: 查询文本
            level: 限定层级（None = 搜索所有层级）
            top_k: 返回数量

        Returns:
            (条目, 相关度) 列表
        """
        query_lower = query.lower()
        results: List[Tuple[MemoryEntry, float]] = []

        for entry in self._entries.values():
            if level and entry.level != level:
                continue

            content_lower = entry.content.lower()
            # 简单的关键词匹配评分
            score = 0.0
            for word in query_lower.split():
                if word in content_lower:
                    score += 0.3
            # 完全包含加分
            if query_lower in content_lower:
                score += 0.5

            score *= entry.effective_score()

            if score > 0:
                results.append((entry, score))

        results.sort(key=lambda x: x[1], reverse=True)

        # 更新访问
        for entry, _ in results[:top_k]:
            entry.access()

        return results[:top_k]

    # ------------------------------------------------------------------
    # 生命周期操作
    # ------------------------------------------------------------------

    def promote_entry(self, entry_id: str) -> Optional[LifecycleEvent]:
        """晋升记忆条目（Working → Episodic → Semantic）。

        晋升条件：
        - Working → Episodic: 访问次数 >= threshold 且重要性 >= min
        - Episodic → Semantic: 访问次数 >= threshold*2 且存在相似条目

        Args:
            entry_id: 条目 ID

        Returns:
            生命周期事件
        """
        entry = self._entries.get(entry_id)
        if not entry:
            return None

        old_level = entry.level
        new_level = None

        if entry.level == MemoryLevel.WORKING:
            if (entry.access_count >= self.promotion_threshold
                    and entry.importance >= self.promotion_min_importance):
                entry.level = MemoryLevel.EPISODIC
                new_level = MemoryLevel.EPISODIC

        elif entry.level == MemoryLevel.EPISODIC:
            if entry.access_count >= self.promotion_threshold * 2:
                # 检查是否有相似条目可以合并
                similar = self._find_similar_entries(entry)
                if similar or entry.confidence >= 0.8:
                    entry.level = MemoryLevel.SEMANTIC
                    new_level = MemoryLevel.SEMANTIC

        if new_level:
            self._promotions_count += 1
            event = LifecycleEvent(
                timestamp=time.time(),
                action=LifecycleAction.PROMOTE,
                entry_id=entry_id,
                from_level=old_level,
                to_level=new_level,
                details={
                    "access_count": entry.access_count,
                    "importance": entry.importance,
                    "confidence": entry.confidence,
                },
            )
            self._events.append(event)
            logger.info(
                "记忆晋升: %s (%s → %s)",
                entry_id, old_level.value, new_level.value,
            )
            return event

        return None

    def distill_entries(
        self,
        source_level: MemoryLevel,
        target_level: MemoryLevel,
    ) -> List[LifecycleEvent]:
        """蒸馏记忆条目。

        将同层级的相似条目合并蒸馏到下一层级。

        Args:
            source_level: 源层级
            target_level: 目标层级

        Returns:
            生命周期事件列表
        """
        events = []
        source_entries = self.get_entries_by_level(source_level)

        # 查找可合并的条目组
        groups = self._find_mergeable_groups(source_entries)

        for group in groups:
            if len(group) < 2:
                continue

            # 选择代表性条目（访问次数最多的）
            representative = max(group, key=lambda e: e.access_count)

            # 合并内容
            merged_content = self._merge_contents(group)
            representative.content = merged_content
            representative.level = target_level
            representative.access_count += sum(e.access_count for e in group[1:])
            representative.metadata["distilled_from"] = [e.entry_id for e in group]

            # 标记其他条目为已蒸馏
            for entry in group[1:]:
                self.remove_entry(entry.entry_id)

            self._distillations_count += 1
            event = LifecycleEvent(
                timestamp=time.time(),
                action=LifecycleAction.DISTILL,
                entry_id=representative.entry_id,
                from_level=source_level,
                to_level=target_level,
                details={
                    "merged_count": len(group),
                    "group_ids": [e.entry_id for e in group],
                },
            )
            events.append(event)

        if events:
            logger.info(
                "蒸馏完成: %d 个组被合并 (%s → %s)",
                len(events), source_level.value, target_level.value,
            )

        return events

    def decay_entries(self) -> List[LifecycleEvent]:
        """衰减记忆条目。

        基于时间和访问模式衰减所有条目。

        Returns:
            衰减事件列表
        """
        events = []
        now = time.time()

        for entry in list(self._entries.values()):
            # 计算时间差（小时）
            age_hours = (now - entry.last_accessed) / 3600.0

            # 指数衰减
            decay_amount = self.decay_rate_hourly * age_hours
            new_factor = max(
                self.min_decay_factor,
                entry.decay_factor * (1 - decay_amount),
            )

            if new_factor != entry.decay_factor:
                old_factor = entry.decay_factor
                entry.decay_factor = new_factor
                self._decays_count += 1

                event = LifecycleEvent(
                    timestamp=now,
                    action=LifecycleAction.DECAY,
                    entry_id=entry.entry_id,
                    details={
                        "old_factor": old_factor,
                        "new_factor": new_factor,
                        "age_hours": age_hours,
                    },
                )
                events.append(event)

        return events

    def expire_entries(self) -> List[LifecycleEvent]:
        """过期删除。

        删除超过最大保留时间的条目。

        Returns:
            过期事件列表
        """
        events = []
        now = time.time()

        for entry in list(self._entries.values()):
            max_age = self._get_max_age(entry.level)
            age = now - entry.last_accessed

            if age > max_age:
                self.remove_entry(entry.entry_id)
                self._expirations_count += 1

                event = LifecycleEvent(
                    timestamp=now,
                    action=LifecycleAction.EXPIRE,
                    entry_id=entry.entry_id,
                    from_level=entry.level,
                    details={
                        "age_seconds": age,
                        "max_age": max_age,
                    },
                )
                events.append(event)

        if events:
            logger.info("过期删除: %d 个条目", len(events))

        return events

    def run_lifecycle_cycle(
        self,
        force_all: bool = False,
    ) -> Dict[str, Any]:
        """执行完整的生命周期检查循环。

        流程：
        1. 衰减所有条目
        2. 过期删除
        3. 尝试晋升 Working → Episodic
        4. 尝试晋升 Episodic → Semantic（蒸馏）

        Args:
            force_all: 是否强制执行所有操作

        Returns:
            操作统计
        """
        results = {
            "decays": 0,
            "expirations": 0,
            "promotions": 0,
            "distillations": 0,
            "total_events": 0,
        }

        # 1. 衰减
        decay_events = self.decay_entries()
        results["decays"] = len(decay_events)

        # 2. 过期
        expire_events = self.expire_entries()
        results["expirations"] = len(expire_events)

        # 3. 晋升
        working_entries = self.get_entries_by_level(MemoryLevel.WORKING)
        for entry in working_entries:
            if force_all or entry.access_count >= self.promotion_threshold:
                event = self.promote_entry(entry.entry_id)
                if event:
                    results["promotions"] += 1

        # 4. 蒸馏
        if self.auto_consolidate or force_all:
            distill_events = self.distill_entries(
                MemoryLevel.EPISODIC,
                MemoryLevel.SEMANTIC,
            )
            results["distillations"] = len(distill_events)

        # 汇总
        results["total_events"] = (
            results["decays"]
            + results["expirations"]
            + results["promotions"]
            + results["distillations"]
        )

        return results

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _get_max_age(self, level: MemoryLevel) -> float:
        """获取层级的最大保留时间。"""
        ages = {
            MemoryLevel.WORKING: self.working_max_age,
            MemoryLevel.EPISODIC: self.episodic_max_age,
            MemoryLevel.SEMANTIC: self.semantic_max_age,
        }
        return ages.get(level, self.working_max_age)

    def _find_similar_entries(
        self,
        entry: MemoryEntry,
        min_similarity: float = 0.5,
    ) -> List[MemoryEntry]:
        """查找与给定条目相似的条目。"""
        similar = []
        entry_content_lower = entry.content.lower()

        for other in self._entries.values():
            if other.entry_id == entry.entry_id:
                continue
            if other.level != entry.level:
                continue

            # 简单的关键词重叠度计算
            words_a = set(entry_content_lower.split())
            words_b = set(other.content.lower().split())

            if words_a and words_b:
                overlap = len(words_a & words_b) / max(len(words_a | words_b), 1)
                if overlap >= min_similarity:
                    similar.append(other)

        return similar

    def _find_mergeable_groups(
        self,
        entries: List[MemoryEntry],
    ) -> List[List[MemoryEntry]]:
        """查找可合并的条目组。"""
        if not entries:
            return []

        groups: List[List[MemoryEntry]] = []
        used_ids: set = set()

        for i, entry_a in enumerate(entries):
            if entry_a.entry_id in used_ids:
                continue

            group = [entry_a]
            used_ids.add(entry_a.entry_id)

            # 查找与 entry_a 相似的条目
            similar = self._find_similar_entries(entry_a)
            for s in similar:
                if s.entry_id not in used_ids:
                    group.append(s)
                    used_ids.add(s.entry_id)

            if len(group) >= 2:
                groups.append(group)

        return groups

    def _merge_contents(self, entries: List[MemoryEntry]) -> str:
        """合并多个条目的内容。"""
        # 使用第一个条目的内容，追加其他条目的摘要
        if not entries:
            return ""

        primary = entries[0]
        extras = entries[1:]

        if not extras:
            return primary.content

        # 追加其他内容
        merged_parts = [primary.content]
        for extra in extras:
            # 如果内容不同，追加摘要
            if extra.content != primary.content:
                merged_parts.append(f"[关联] {extra.content[:100]}")

        return "\n".join(merged_parts)

    # ------------------------------------------------------------------
    # 统计
    # ------------------------------------------------------------------

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息。"""
        level_counts = {}
        for level in MemoryLevel:
            count = len(self.get_entries_by_level(level))
            level_counts[level.value] = count

        return {
            "total_entries": len(self._entries),
            "level_counts": level_counts,
            "promotions_total": self._promotions_count,
            "distillations_total": self._distillations_count,
            "decays_total": self._decays_count,
            "expirations_total": self._expirations_count,
            "events_count": len(self._events),
            "config": {
                "promotion_threshold": self.promotion_threshold,
                "distillation_threshold": self.distillation_threshold,
                "decay_rate_hourly": self.decay_rate_hourly,
            },
        }

    def get_recent_events(
        self,
        limit: int = 10,
        action: Optional[LifecycleAction] = None,
    ) -> List[LifecycleEvent]:
        """获取最近的生命周期事件。"""
        events = self._events
        if action:
            events = [e for e in events if e.action == action]
        return events[-limit:]

    def clear_events(self) -> None:
        """清空事件历史。"""
        self._events.clear()

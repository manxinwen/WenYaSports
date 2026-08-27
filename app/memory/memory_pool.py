"""MemoryPool: 按用户隔离的分级记忆池。

为每个用户维护独立的 HierarchicalMemory 实例，
确保用户数据完全隔离，防止数据泄露和串扰。

Architecture:
    MemoryPool
    ├── user_001 → HierarchicalMemory (working + episodic + semantic)
    ├── user_002 → HierarchicalMemory
    └── user_N   → HierarchicalMemory

Features:
- 懒加载: 首次访问时创建用户记忆实例
- 自动回收: 支持过期清理不活跃的用户记忆
- 线程安全: 使用锁保护并发访问
- 容量限制: 限制最大缓存的用户数，防止内存泄漏

Usage:
    pool = MemoryPool(max_users=1000)
    memory = pool.get_or_create("user_001")
    memory.store("用户完成了5km跑步", level="episodic")
    results = memory.retrieve("跑步", top_k=5)
"""

from __future__ import annotations

import logging
import threading
import time
from collections import OrderedDict
from typing import Any, Dict, List, Optional

from app.memory.hierarchical_memory import HierarchicalMemory

logger = logging.getLogger(__name__)


class MemoryPool:
    """按用户隔离的分级记忆池。

    使用 LRU (Least Recently Used) 策略管理用户记忆实例，
    当用户数超过 max_users 时，自动淘汰最久未访问的用户记忆。

    Thread Safety:
        使用 RLock 保护所有池操作，确保并发安全。

    Memory Isolation:
        每个用户拥有独立的 HierarchicalMemory 实例，
        包括 WorkingMemory、EpisodicMemory 和 SemanticMemory 三层。
    """

    def __init__(
        self,
        max_users: int = 1000,
        working_max: int = 50,
        episodic_max: int = 1000,
        semantic_max: int = 5000,
        ttl_seconds: Optional[float] = None,
    ):
        """初始化记忆池。

        Args:
            max_users: 最大缓存的用户数（LRU 淘汰）
            working_max: 工作记忆最大条目数
            episodic_max: 情节记忆最大条目数
            semantic_max: 语义记忆最大条目数
            ttl_seconds: 工作记忆 TTL（None 则不自动过期）
        """
        self._max_users = max_users
        self._memory_config = {
            "working_max": working_max,
            "episodic_max": episodic_max,
            "semantic_max": semantic_max,
            "working_ttl": ttl_seconds,
        }

        # OrderedDict 实现 LRU: {user_id: (HierarchicalMemory, last_access_time)}
        self._pool: OrderedDict[str, tuple] = OrderedDict()
        self._lock = threading.RLock()

    def get_or_create(self, user_id: str) -> HierarchicalMemory:
        """获取或创建用户的分级记忆实例。

        如果用户已存在，更新访问时间并移到 LRU 末尾。
        如果用户不存在，创建新实例并检查容量限制。

        Args:
            user_id: 用户唯一标识

        Returns:
            用户的 HierarchicalMemory 实例
        """
        with self._lock:
            if user_id in self._pool:
                # 访问已有用户: 移到 LRU 末尾
                memory, _ = self._pool.pop(user_id)
                self._pool[user_id] = (memory, time.time())
                return memory

            # 新用户: 检查容量
            if len(self._pool) >= self._max_users:
                self._evict_one()

            # 创建新实例
            memory = HierarchicalMemory(**self._memory_config)
            self._pool[user_id] = (memory, time.time())
            logger.debug("Created new memory for user: %s (total users: %d)", user_id, len(self._pool))
            return memory

    def get(self, user_id: str) -> Optional[HierarchicalMemory]:
        """获取用户记忆（不创建，不存在则返回 None）。

        Args:
            user_id: 用户唯一标识

        Returns:
            HierarchicalMemory 或 None
        """
        with self._lock:
            if user_id in self._pool:
                memory, _ = self._pool.pop(user_id)
                self._pool[user_id] = (memory, time.time())
                return memory
            return None

    def remove(self, user_id: str) -> bool:
        """移除用户的记忆实例。

        Args:
            user_id: 用户唯一标识

        Returns:
            是否成功移除
        """
        with self._lock:
            if user_id in self._pool:
                del self._pool[user_id]
                logger.info("Removed memory for user: %s", user_id)
                return True
            return False

    def store(self, user_id: str, content: str, level: str = "auto",
              metadata: Optional[Dict[str, Any]] = None, **kwargs) -> Dict[str, Any]:
        """为用户存储记忆。

        Args:
            user_id: 用户唯一标识
            content: 记忆内容
            level: 目标层 - "working" | "episodic" | "semantic" | "auto"
            metadata: 元数据

        Returns:
            存储结果
        """
        memory = self.get_or_create(user_id)
        return memory.store(content=content, level=level, metadata=metadata, **kwargs)

    def retrieve(self, user_id: str, query: str, level: Optional[str] = None,
                 top_k: int = 5) -> List[Dict[str, Any]]:
        """为用户检索记忆。

        Args:
            user_id: 用户唯一标识
            query: 查询文本
            level: 限定层级（None 则跨层搜索）
            top_k: 返回结果数

        Returns:
            检索结果列表
        """
        memory = self.get_or_create(user_id)
        return memory.retrieve(query=query, level=level, top_k=top_k)

    def get_stats(self) -> Dict[str, Any]:
        """获取记忆池统计信息。"""
        with self._lock:
            total_users = len(self._pool)
            total_entries = 0
            users_details = []

            for user_id, (memory, last_access) in self._pool.items():
                state = memory.get_stats()
                working_count = state.get("working_count", 0)
                episodic_count = state.get("episodic_count", 0)
                semantic_count = state.get("semantic_count", 0)
                total_entries += working_count + episodic_count + semantic_count

                users_details.append({
                    "user_id": user_id,
                    "last_access": last_access,
                    "working_count": working_count,
                    "episodic_count": episodic_count,
                    "semantic_count": semantic_count,
                })

            return {
                "total_users": total_users,
                "max_users": self._max_users,
                "total_entries": total_entries,
                "users": users_details,
            }

    def _evict_one(self) -> None:
        """淘汰最久未访问的用户（LRU）。"""
        if not self._pool:
            return

        # OrderedDict 的第一个元素是最久未访问的
        oldest_user, _ = next(iter(self._pool.items()))
        self._pool.pop(oldest_user)
        logger.info("Evicted LRU user memory: %s (remaining: %d)", oldest_user, len(self._pool))

    def clear(self) -> None:
        """清空所有用户记忆。"""
        with self._lock:
            self._pool.clear()
            logger.info("Memory pool cleared")

    @property
    def user_count(self) -> int:
        """当前缓存的用户数。"""
        with self._lock:
            return len(self._pool)


# ---------------------------------------------------------------------------
# 全局 MemoryPool 单例（进程级，按 user_id 隔离实例）
# ---------------------------------------------------------------------------
_global_pool: Optional[MemoryPool] = None


def get_memory_pool(max_users: int = 1000) -> MemoryPool:
    """获取全局 MemoryPool 实例。

    Args:
        max_users: 最大用户数（仅首次创建时生效）

    Returns:
        MemoryPool 实例
    """
    global _global_pool
    if _global_pool is None:
        _global_pool = MemoryPool(max_users=max_users)
    return _global_pool

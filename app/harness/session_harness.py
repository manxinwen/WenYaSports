"""SessionHarness: 请求级会话 Harness。

为每个用户请求提供独立的 Harness 实例，确保：
1. Blackboard 数据完全隔离
2. Agent 执行上下文独立
3. 会话状态可追溯

Architecture:
    Request → SessionHarness(user_id) → Isolated Blackboard → Agents

    Session Pool:
    ├── user_001 → SessionHarness (isolated blackboard + session context)
    ├── user_002 → SessionHarness
    └── user_N   → SessionHarness

Features:
- 懒加载: 首次访问时创建会话实例
- 自动回收: 支持过期清理不活跃会话
- 线程安全: 锁保护并发访问
- 资源复用: Agent 实例可共享（只读），Blackboard 独立

Usage:
    pool = SessionPool()
    session = pool.get_or_create("user_001", "sess_abc")
    session.harness.run_workflow(...)
    pool.remove("user_001", "sess_abc")
"""

from __future__ import annotations

import logging
import threading
import time
from collections import OrderedDict
from typing import Any, Dict, List, Optional, Tuple

from app.harness.harness import Harness
from app.harness.blackboard import Blackboard
from app.harness.message_bus import MessageBus
from app.harness.agent_registry import AgentRegistry
from app.harness.governance import GovernanceEngine
from app.harness_setup import create_harness
from app.models.user_context import UserContext

logger = logging.getLogger(__name__)


class SessionHarness:
    """请求级会话 Harness。

    为单个用户会话提供独立的 Harness 环境，
    包含独立的 Blackboard、会话上下文和 Agent 引用。

    Isolation Guarantees:
    - Blackboard: 每个会话独立的 Blackboard 实例
    - Session Context: 会话状态仅对当前请求可见
    - Trace: 执行追踪按会话隔离
    """

    def __init__(self, user_id: str, session_id: str):
        """初始化会话 Harness。

        Args:
            user_id: 用户唯一标识
            session_id: 会话唯一标识
        """
        self.user_id = user_id
        self.session_id = session_id
        self.created_at = time.time()
        self.last_accessed = time.time()

        # 创建隔离的 Harness 实例
        self.harness = Harness()

        # 注册 Agent（复用全局注册逻辑，但在独立 Blackboard 上）
        self._register_agents()

        # 初始化会话上下文
        self._context = UserContext(
            user_id=user_id,
            session_id=session_id,
        )

        # 写入系统级配置
        self.harness.blackboard.write(
            "system",
            "session_info",
            {
                "user_id": user_id,
                "session_id": session_id,
                "created_at": self.created_at,
                "isolation": "session_scoped",
            },
        )

        logger.debug(
            "SessionHarness created: user=%s, session=%s",
            user_id, session_id,
        )

    def _register_agents(self) -> None:
        """在会话 Harness 上注册所有 Agent。

        复用 create_harness 中的 Agent 注册逻辑，
        但使用独立的 Blackboard。
        """
        from app.agents.parser_agent import ParserAgent
        from app.agents.feature_extractor_agent import FeatureExtractorAgent
        from app.agents.memory_agent import MemoryAgent
        from app.agents.recommendation_agent import RecommendationAgent
        from app.agents.reaact_agent import ReActAgent
        from mcp_plugins import PluginManager

        harness = self.harness

        # 1. ParserAgent
        parser = ParserAgent()
        harness.register_agent(
            agent_instance=parser,
            agent_id="parser",
            name="FIT Parser",
            capabilities=["fit_parsing", "csv_parsing", "data_extraction", "metadata_parsing"],
            version="1.0.0",
            dependencies=[],
            metadata={
                "description": "Parses FIT and CSV activity files",
                "input_types": [".fit", ".csv"],
                "output_types": ["ParsedActivity"],
            },
        )

        # 2. FeatureExtractorAgent
        feature_extractor = FeatureExtractorAgent()
        harness.register_agent(
            agent_instance=feature_extractor,
            agent_id="feature_extractor",
            name="Feature Extractor",
            capabilities=["feature_engineering", "statistics", "intensity_distribution"],
            version="1.0.0",
            dependencies=["fit_parsing"],
            metadata={
                "description": "Extracts training metrics and statistics",
                "computes": ["distance", "duration", "elevation", "heart_rate_zones"],
            },
        )

        # 3. MemoryAgent
        memory = MemoryAgent()
        harness.register_agent(
            agent_instance=memory,
            agent_id="memory",
            name="Memory Manager",
            capabilities=["user_profile", "context_retrieval", "memory_update"],
            version="1.0.0",
            dependencies=[],
            metadata={
                "description": "Manages user profiles and training history",
                "storage": "SQLite + Vector DB",
            },
        )

        # 4. RecommendationAgent
        recommender = RecommendationAgent()
        harness.register_agent(
            agent_instance=recommender,
            agent_id="recommender",
            name="Recommendation Engine",
            capabilities=["training_advice", "rule_engine", "llm_generation"],
            version="1.0.0",
            dependencies=["feature_engineering", "user_profile"],
            metadata={
                "description": "Generates personalized training recommendations",
                "methods": ["rules", "llm", "hybrid"],
            },
        )

        # 5. ReActAgent
        plugin_manager = PluginManager()
        react = ReActAgent(plugin_manager=plugin_manager)
        harness.register_agent(
            agent_instance=react,
            agent_id="react",
            name="ReAct Agent",
            capabilities=["tool_calling", "reasoning", "multi_step_planning"],
            version="1.0.0",
            dependencies=["memory_update", "training_advice"],
            metadata={
                "description": "ReAct pattern agent for complex queries",
                "tools_available": plugin_manager.get_all_tools(),
            },
        )

        # 配置消息路由
        harness.message_bus.subscribe(
            "memory",
            lambda msg: logger.debug("Memory received: %s", msg.message_type.value),
        )
        harness.message_bus.subscribe(
            "recommender",
            lambda msg: logger.debug("Recommender received: %s", msg.message_type.value),
        )

        # 写入系统配置
        harness.blackboard.write(
            "system",
            "config",
            {
                "harness_version": "2.0.0-session",
                "architecture": "Session-Scoped Multi-Agent Harness",
                "design_pattern": "Orchestration + Isolated Blackboard + Message Bus",
                "total_agents": len(harness.registry.list_agents()),
                "capabilities": harness.registry.get_available_capabilities(),
            },
        )

    @property
    def context(self) -> UserContext:
        """获取当前会话的用户上下文。"""
        self.last_accessed = time.time()
        return self._context

    def update_access_time(self) -> None:
        """更新最后访问时间。"""
        self.last_accessed = time.time()

    def get_stats(self) -> Dict[str, Any]:
        """获取会话统计信息。"""
        return {
            "user_id": self.user_id,
            "session_id": self.session_id,
            "created_at": self.created_at,
            "last_accessed": self.last_accessed,
            "age_seconds": time.time() - self.created_at,
            "idle_seconds": time.time() - self.last_accessed,
            "blackboard_stats": self.harness.blackboard.get_stats(),
            "registered_agents": self.harness.registry.list_agents(),
        }


class SessionPool:
    """会话池，管理多个用户会话的 Harness 实例。

    使用 LRU 策略管理会话，支持自动回收过期会话。

    Thread Safety:
        使用 RLock 保护所有池操作。
    """

    def __init__(
        self,
        max_sessions: int = 500,
        session_ttl: float = 3600.0,
    ):
        """初始化会话池。

        Args:
            max_sessions: 最大会话数（LRU 淘汰）
            session_ttl: 会话存活时间（秒），超过则回收
        """
        self._max_sessions = max_sessions
        self._session_ttl = session_ttl

        # OrderedDict 实现 LRU: {(user_id, session_id): SessionHarness}
        self._pool: OrderedDict[Tuple[str, str], SessionHarness] = OrderedDict()
        self._lock = threading.RLock()

    def get_or_create(self, user_id: str, session_id: str) -> SessionHarness:
        """获取或创建用户会话。

        Args:
            user_id: 用户唯一标识
            session_id: 会话唯一标识

        Returns:
            SessionHarness 实例
        """
        key = (user_id, session_id)

        with self._lock:
            if key in self._pool:
                session = self._pool.pop(key)
                session.update_access_time()
                self._pool[key] = session
                return session

            # 检查容量
            if len(self._pool) >= self._max_sessions:
                self._evict_expired()
                if len(self._pool) >= self._max_sessions:
                    self._evict_one()

            # 创建新会话
            session = SessionHarness(user_id=user_id, session_id=session_id)
            self._pool[key] = session
            logger.debug(
                "Session created: user=%s, session=%s, total=%d",
                user_id, session_id, len(self._pool),
            )
            return session

    def get(self, user_id: str, session_id: str) -> Optional[SessionHarness]:
        """获取会话（不创建）。

        Args:
            user_id: 用户唯一标识
            session_id: 会话唯一标识

        Returns:
            SessionHarness 或 None
        """
        key = (user_id, session_id)
        with self._lock:
            if key in self._pool:
                session = self._pool.pop(key)
                session.update_access_time()
                self._pool[key] = session
                return session
            return None

    def remove(self, user_id: str, session_id: str) -> bool:
        """移除会话。

        Args:
            user_id: 用户唯一标识
            session_id: 会话唯一标识

        Returns:
            是否成功移除
        """
        key = (user_id, session_id)
        with self._lock:
            if key in self._pool:
                session = self._pool.pop(key)
                logger.info(
                    "Session removed: user=%s, session=%s",
                    user_id, session_id,
                )
                return True
            return False

    def get_user_sessions(self, user_id: str) -> List[SessionHarness]:
        """获取用户的所有活跃会话。

        Args:
            user_id: 用户唯一标识

        Returns:
            会话列表
        """
        with self._lock:
            sessions = []
            for (uid, sid), session in self._pool.items():
                if uid == user_id:
                    sessions.append(session)
            return sessions

    def remove_user_sessions(self, user_id: str) -> int:
        """移除用户的所有会话。

        Args:
            user_id: 用户唯一标识

        Returns:
            移除的会话数
        """
        with self._lock:
            to_remove = [
                key for key in self._pool
                if key[0] == user_id
            ]
            for key in to_remove:
                del self._pool[key]
            if to_remove:
                logger.info(
                    "Removed %d sessions for user: %s",
                    len(to_remove), user_id,
                )
            return len(to_remove)

    def cleanup_expired(self) -> int:
        """清理所有过期会话。

        Returns:
            清理的会话数
        """
        return self._evict_expired()

    def _evict_expired(self) -> int:
        """淘汰所有过期会话。"""
        now = time.time()
        expired_keys = []

        for key, session in self._pool.items():
            if now - session.last_accessed > self._session_ttl:
                expired_keys.append(key)

        for key in expired_keys:
            del self._pool[key]
            logger.debug("Expired session evicted: %s", key)

        if expired_keys:
            logger.info(
                "Evicted %d expired sessions (remaining: %d)",
                len(expired_keys), len(self._pool),
            )

        return len(expired_keys)

    def _evict_one(self) -> None:
        """淘汰最久未访问的会话（LRU）。"""
        if not self._pool:
            return

        oldest_key, _ = next(iter(self._pool.items()))
        self._pool.pop(oldest_key)
        logger.info(
            "Evicted LRU session: %s (remaining: %d)",
            oldest_key, len(self._pool),
        )

    def get_stats(self) -> Dict[str, Any]:
        """获取会话池统计信息。"""
        with self._lock:
            # 统计每个用户的会话数
            user_counts = {}
            for (uid, sid) in self._pool:
                user_counts[uid] = user_counts.get(uid, 0) + 1

            return {
                "total_sessions": len(self._pool),
                "max_sessions": self._max_sessions,
                "session_ttl": self._session_ttl,
                "total_users": len(user_counts),
                "user_session_counts": user_counts,
            }

    def clear(self) -> None:
        """清空所有会话。"""
        with self._lock:
            self._pool.clear()
            logger.info("Session pool cleared")

    @property
    def session_count(self) -> int:
        """当前活跃会话数。"""
        with self._lock:
            return len(self._pool)


# ---------------------------------------------------------------------------
# 全局 SessionPool 单例
# ---------------------------------------------------------------------------
_global_session_pool: Optional[SessionPool] = None


def get_session_pool(max_sessions: int = 500, session_ttl: float = 3600.0) -> SessionPool:
    """获取全局 SessionPool 实例。

    Args:
        max_sessions: 最大会话数（仅首次创建时生效）
        session_ttl: 会话 TTL（仅首次创建时生效）

    Returns:
        SessionPool 实例
    """
    global _global_session_pool
    if _global_session_pool is None:
        _global_session_pool = SessionPool(
            max_sessions=max_sessions,
            session_ttl=session_ttl,
        )
    return _global_session_pool

"""MemoryAgent: short-term (TTL cache) + long-term (SQLite) memory."""

import json
import logging
from datetime import datetime, timedelta
from typing import Optional

from cachetools import TTLCache

from app.agents.base_agent import BaseAgent
from app.db import database
from app.models.features import ActivityFeatures
from app.models.recommendation import Recommendation

logger = logging.getLogger(__name__)

MAX_CACHE_SIZE = 100
DEFAULT_TTL = 1800  # 30 minutes


class MemoryAgent(BaseAgent):
    """Manages short-term session context and long-term user memory.

    Supports Harness integration for:
    - Trace recording for observability
    - Message-based communication with other agents
    - Blackboard data sharing
    """

    agent_id = "memory"
    agent_name = "Memory Manager"
    capabilities = ["user_profile", "context_retrieval", "memory_update"]

    def __init__(self, db_path: Optional[str] = None, short_term_ttl: int = DEFAULT_TTL):
        self.short_term_cache = TTLCache(maxsize=MAX_CACHE_SIZE, ttl=short_term_ttl)
        self.db_path = db_path
        database.init_db(db_path)

    def run(self, user_id: str, session_id: str) -> dict:
        """Alias for get_context, keeps the BaseAgent interface."""
        self._execution_count += 1
        self._last_input = f"user_id={user_id}"

        self._trace_step(
            step_type="thought",
            thought=f"加载用户上下文: user_id={user_id}",
            detail={"user_id": user_id, "session_id": session_id},
        )

        result = self.get_context(user_id, session_id)
        self._last_output = result

        self._trace_step(
            step_type="final",
            thought=f"用户上下文加载完成",
            detail={
                "has_profile": bool(result.get("user_profile")),
                "recent_load_7d": result.get("recent_load_7d", 0),
            },
        )

        if self.message_bus:
            self.broadcast_message(
                message_type="agent_completed",
                payload={
                    "agent_id": self.agent_id,
                    "status": "success",
                    "user_id": user_id,
                },
            )

        return result

    def _sum_load_since(self, user_id: str, days: int) -> float:
        rows = database.get_recent_activities(user_id, limit=1000, db_path=self.db_path)
        cutoff = datetime.now() - timedelta(days=days)
        total = 0.0
        for row in rows:
            try:
                activity_date = datetime.fromisoformat(row["date"])
                features = json.loads(row["features_json"])
            except (ValueError, TypeError, json.JSONDecodeError):
                continue
            if activity_date >= cutoff:
                total += float(features.get("training_load", 0.0))
        return total

    def get_context(self, user_id: str, session_id: str) -> dict:
        """Return user profile + recent 7-day load (+ cached session context if any)."""
        cached = self.short_term_cache.get(session_id)
        if cached is not None:
            return cached

        profile = database.get_user_profile(user_id, self.db_path) or {}
        recent_load_7d = self._sum_load_since(user_id, days=7)
        return {
            "user_profile": profile,
            "recent_load_7d": recent_load_7d,
            "short_term_context": {},
        }

    def update(
        self,
        user_id: str,
        session_id: str,
        features: ActivityFeatures,
        recommendation: Recommendation,
        metadata: Optional[dict] = None,
        file_path: Optional[str] = None,
    ) -> None:
        """Persist the activity and refresh profile + short-term cache."""
        self._trace_step(
            step_type="thought",
            thought=f"持久化活动数据: user_id={user_id}",
            detail={
                "features_load": features.training_load,
                "has_recommendation": bool(recommendation),
            },
        )

        now = datetime.now()
        features_json = features.model_dump_json()
        recommendation_json = recommendation.model_dump_json()
        metadata_json = json.dumps(metadata or {}, ensure_ascii=False)

        database.insert_activity(
            user_id,
            now.isoformat(),
            features_json,
            metadata_json,
            recommendation_json,
            file_path=file_path,
            db_path=self.db_path,
        )

        # Recompute rolling training load averages and update the user profile
        profile = database.get_user_profile(user_id, self.db_path) or {}
        load_7d = self._sum_load_since(user_id, days=7)
        load_42d = self._sum_load_since(user_id, days=42)
        profile.update({"avg_load_7d": load_7d, "avg_load_42d": load_42d})
        database.save_user_profile(user_id, profile, self.db_path)

        # Update short-term (session) memory
        self.short_term_cache[session_id] = {
            "user_profile": profile,
            "recent_load_7d": load_7d,
            "short_term_context": {
                "last_features": features.model_dump(),
                "last_recommendation": recommendation.model_dump(),
                "last_activity_at": now.isoformat(),
            },
        }

        self._trace_step(
            step_type="final",
            thought=f"用户记忆更新完成: 7日负荷={load_7d:.1f}, 42日负荷={load_42d:.1f}",
            detail={
                "avg_load_7d": load_7d,
                "avg_load_42d": load_42d,
                "cache_updated": True,
            },
        )

        if self.blackboard:
            self.write_to_blackboard(
                namespace="memory_state",
                key=f"user_{user_id}",
                value={
                    "avg_load_7d": load_7d,
                    "avg_load_42d": load_42d,
                    "profile_updated_at": now.isoformat(),
                },
            )

        if self.message_bus:
            self.broadcast_message(
                message_type="memory_updated",
                payload={
                    "agent_id": self.agent_id,
                    "user_id": user_id,
                    "update_type": "activity_persisted",
                },
            )

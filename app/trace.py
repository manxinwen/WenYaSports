"""Agent Trace Collector for Observability.

Provides a lightweight, in-memory trace collector that records every step
an agent takes (thought, action, tool call, observation). This data is
exposed via API to power the Agent Trace Dashboard and Reasoning Replay
UI for the frontend.
"""

import time
from typing import Any, Dict, List, Optional
from collections import defaultdict
from datetime import datetime


class TraceStep:
    """A single step in an agent's trace."""

    def __init__(
        self,
        agent_name: str,
        step_type: str,
        detail: Dict[str, Any],
        thought: Optional[str] = None,
        timestamp: Optional[float] = None,
    ):
        self.agent_name = agent_name
        self.step_type = step_type  # thought, action, tool_call, observation, final
        self.detail = detail
        self.thought = thought
        self.timestamp = timestamp or time.time()

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for JSON API."""
        return {
            "agent_name": self.agent_name,
            "step_type": self.step_type,
            "thought": self.thought,
            "detail": self.detail,
            "timestamp": self.timestamp,
            "time_str": datetime.fromtimestamp(self.timestamp).strftime(
                "%H:%M:%S"
            ),
        }


class TraceCollector:
    """Singleton-like in-memory collector for agent traces."""

    def __init__(self):
        # session_id -> List[TraceStep]
        self._traces: Dict[str, List[TraceStep]] = defaultdict(list)
        # Global history (session summaries) for dashboard
        self._session_history: List[Dict[str, Any]] = []

    def add_step(
        self,
        session_id: str,
        agent_name: str,
        step_type: str,
        detail: Dict[str, Any],
        thought: Optional[str] = None,
    ) -> None:
        """Record a single trace step."""
        step = TraceStep(
            agent_name=agent_name,
            step_type=step_type,
            detail=detail,
            thought=thought,
        )
        self._traces[session_id].append(step)

    def get_trace(self, session_id: str) -> List[Dict[str, Any]]:
        """Get full trace for a session, sorted by timestamp."""
        steps = self._traces.get(session_id, [])
        return [s.to_dict() for s in sorted(steps, key=lambda x: x.timestamp)]

    def get_session_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent session summaries for the dashboard."""
        return sorted(
            self._session_history,
            key=lambda x: x["timestamp"],
            reverse=True,
        )[:limit]

    def record_session_start(
        self, session_id: str, user_request: str, user_id: str = "demo"
    ) -> None:
        """Mark the start of a new session."""
        self._session_history.append(
            {
                "session_id": session_id,
                "user_request": user_request,
                "user_id": user_id,
                "status": "running",
                "timestamp": time.time(),
                "time_str": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "total_steps": 0,
                "agents_used": set(),
            }
        )
        self._traces[session_id] = []

    def record_session_end(
        self, session_id: str, success: bool, total_steps: int
    ) -> None:
        """Mark the end of a session."""
        for sess in self._session_history:
            if sess["session_id"] == session_id:
                sess["status"] = "completed" if success else "failed"
                sess["total_steps"] = total_steps
                sess["agents_used"] = list(
                    {s["agent_name"] for s in self._traces.get(session_id, [])}
                )
                break

    def get_memory_state(self) -> Dict[str, Any]:
        """Get memory system statistics for Memory Inspector UI."""
        return {
            "active_sessions": len(
                [s for s in self._session_history if s["status"] == "running"]
            ),
            "total_sessions": len(self._session_history),
            "total_steps_recorded": sum(
                len(self._traces.get(s_id, []))
                for s_id in [s["session_id"] for s in self._session_history]
            ),
            "agents_tracked": list(
                {
                    step.agent_name
                    for steps in self._traces.values()
                    for step in steps
                }
            ),
            "vector_db_status": {
                "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
                "vector_store": "ChromaDB",
                "collections": ["user_profiles", "training_knowledge"],
            },
        }


# Global trace collector instance
trace_collector = TraceCollector()

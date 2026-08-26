"""Abstract base class for all agents."""

from abc import ABC, abstractmethod
from typing import Optional


class BaseAgent(ABC):
    """All agents in the multi-agent system inherit from this class.
    
    Optional: accepts a trace_collector for observability dashboard.
    """

    def __init__(self, name: str = "base_agent", trace_collector=None):
        self.name = name
        self.trace_collector = trace_collector

    def _trace_step(
        self,
        session_id: str,
        step_type: str,
        detail: dict,
        thought: Optional[str] = None,
    ) -> None:
        """Helper to record trace steps to the collector."""
        if self.trace_collector and session_id:
            self.trace_collector.add_step(
                session_id=session_id,
                agent_name=self.name,
                step_type=step_type,
                detail=detail,
                thought=thought,
            )

    @abstractmethod
    def run(self, *args, **kwargs):
        raise NotImplementedError

"""Abstract base class for all agents."""

from abc import ABC, abstractmethod


class BaseAgent(ABC):
    """All agents in the multi-agent system inherit from this class."""

    @abstractmethod
    def run(self, *args, **kwargs):
        raise NotImplementedError

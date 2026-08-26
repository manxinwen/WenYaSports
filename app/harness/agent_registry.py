"""AgentRegistry: Agent lifecycle management and capability discovery.

Maintains a registry of all agents in the system, including:
- Agent capabilities (what they can do)
- Agent status (idle, running, error)
- Agent metadata (version, config, etc.)
- Dynamic discovery (agents can find each other by capability)
"""

import time
import threading
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
from collections import defaultdict


class AgentStatus(Enum):
    """Agent lifecycle states."""
    REGISTERED = "registered"
    IDLE = "idle"
    RUNNING = "running"
    SUSPENDED = "suspended"
    ERROR = "error"
    TERMINATED = "terminated"


class AgentDescriptor:
    """Metadata and capabilities for a registered agent.

    Attributes:
        agent_id: Unique identifier
        name: Human-readable name
        version: Agent version
        capabilities: List of capabilities this agent provides
        dependencies: List of agents/capabilities this agent requires
        status: Current lifecycle state
        metadata: Additional metadata
    """

    def __init__(
        self,
        agent_id: str,
        name: str,
        version: str = "1.0.0",
        capabilities: Optional[List[str]] = None,
        dependencies: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.agent_id = agent_id
        self.name = name
        self.version = version
        self.capabilities = capabilities or []
        self.dependencies = dependencies or []
        self.status = AgentStatus.REGISTERED
        self.metadata = metadata or {}
        self.registered_at = time.time()
        self.last_active_at = time.time()
        self.execution_count = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "version": self.version,
            "capabilities": self.capabilities,
            "dependencies": self.dependencies,
            "status": self.status.value,
            "metadata": self.metadata,
            "execution_count": self.execution_count,
            "last_active": time.strftime(
                "%Y-%m-%d %H:%M:%S", time.localtime(self.last_active_at)
            ),
        }


class AgentRegistry:
    """Registry for managing agent lifecycles and capabilities.

    Provides:
    - Agent registration/deregistration
    - Status management
    - Capability-based discovery
    - Agent health tracking
    """

    def __init__(self):
        self._agents: Dict[str, AgentDescriptor] = {}
        self._instances: Dict[str, Any] = {}  # Agent instances
        self._capability_index: Dict[str, List[str]] = defaultdict(list)
        self._lock = threading.RLock()

    def register(
        self,
        agent_id: str,
        agent_instance: Any,
        name: str,
        capabilities: List[str],
        version: str = "1.0.0",
        dependencies: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AgentDescriptor:
        """Register a new agent in the system.

        Args:
            agent_id: Unique identifier for the agent
            agent_instance: The actual agent object
            name: Human-readable name
            capabilities: What this agent can do
            version: Agent version string
            dependencies: What this agent depends on
            metadata: Additional info

        Returns:
            The created AgentDescriptor
        """
        with self._lock:
            descriptor = AgentDescriptor(
                agent_id=agent_id,
                name=name,
                version=version,
                capabilities=capabilities,
                dependencies=dependencies,
                metadata=metadata,
            )
            self._agents[agent_id] = descriptor
            self._instances[agent_id] = agent_instance

            # Update capability index
            for cap in capabilities:
                if agent_id not in self._capability_index[cap]:
                    self._capability_index[cap].append(agent_id)

            descriptor.status = AgentStatus.IDLE
            return descriptor

    def deregister(self, agent_id: str) -> bool:
        """Remove an agent from the registry."""
        with self._lock:
            if agent_id in self._agents:
                # Remove from capability index
                for cap in self._agents[agent_id].capabilities:
                    if agent_id in self._capability_index[cap]:
                        self._capability_index[cap].remove(agent_id)

                self._agents[agent_id].status = AgentStatus.TERMINATED
                del self._agents[agent_id]
                del self._instances[agent_id]
                return True
            return False

    def get_descriptor(self, agent_id: str) -> Optional[AgentDescriptor]:
        """Get agent descriptor by ID."""
        return self._agents.get(agent_id)

    def get_instance(self, agent_id: str) -> Optional[Any]:
        """Get the actual agent instance."""
        return self._instances.get(agent_id)

    def set_status(self, agent_id: str, status: AgentStatus) -> None:
        """Update agent status."""
        descriptor = self._agents.get(agent_id)
        if descriptor:
            descriptor.status = status
            descriptor.last_active_at = time.time()

    def get_by_capability(self, capability: str) -> List[str]:
        """Find agents that provide a specific capability.

        Returns:
            List of agent IDs
        """
        return self._capability_index.get(capability, [])

    def find_agent(self, capability: str) -> Optional[str]:
        """Find the first available agent with a capability.

        Returns:
            Agent ID or None
        """
        agents = self._capability_index.get(capability, [])
        for agent_id in agents:
            descriptor = self._agents[agent_id]
            if descriptor.status in (AgentStatus.IDLE, AgentStatus.RUNNING):
                return agent_id
        return agents[0] if agents else None

    def increment_execution(self, agent_id: str) -> int:
        """Increment execution counter and return new count."""
        descriptor = self._agents.get(agent_id)
        if descriptor:
            descriptor.execution_count += 1
            descriptor.last_active_at = time.time()
            return descriptor.execution_count
        return 0

    def list_agents(self) -> List[Dict[str, Any]]:
        """Get all registered agents and their status."""
        return [d.to_dict() for d in self._agents.values()]

    def get_available_capabilities(self) -> List[str]:
        """Get all unique capabilities in the system."""
        return list(self._capability_index.keys())

    def get_stats(self) -> Dict[str, Any]:
        """Get registry statistics."""
        status_counts = defaultdict(int)
        for d in self._agents.values():
            status_counts[d.status.value] += 1

        return {
            "total_agents": len(self._agents),
            "status_distribution": dict(status_counts),
            "total_capabilities": len(self._capability_index),
            "total_executions": sum(
                d.execution_count for d in self._agents.values()
            ),
        }

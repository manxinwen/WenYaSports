"""Abstract base class for all agents.

Supports both standalone and Harness-based execution modes.
Agents can optionally be registered with a Harness to gain access to:
- Blackboard (shared state)
- MessageBus (inter-agent communication)
- GovernanceEngine (safety constraints)
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from app.trace import trace_collector


class BaseAgent(ABC):
    """All agents in the multi-agent system inherit from this class.

    Supports optional Harness integration for:
    - Inter-agent communication via message_bus
    - Shared state via blackboard
    - Governance and budget controls

    Usage:
        # Standalone mode
        agent = MyAgent()
        result = agent.run(input_data)

        # Harness mode (registered with harness)
        harness.register_agent(agent, "my_agent", ...)
    """

    # Class-level agent metadata (can be overridden by subclasses)
    agent_id: str = "base_agent"
    agent_name: str = "Base Agent"
    version: str = "1.0.0"
    capabilities: List[str] = []
    dependencies: List[str] = []

    def __init__(self, name: Optional[str] = None, trace_collector=None):
        if name:
            self.agent_id = name
            self.agent_name = name.replace("_", " ").title()

        # Harness integration attributes (set by Harness.register_agent)
        self.harness: Optional[Any] = None
        self.blackboard: Optional[Any] = None
        self.message_bus: Optional[Any] = None

        # Trace collector for observability
        self._trace_collector = trace_collector or trace_collector

        # Execution state
        self._execution_count = 0
        self._last_input: Any = None
        self._last_output: Any = None
        self._last_error: Optional[str] = None

    @abstractmethod
    def run(self, *args, **kwargs) -> Any:
        """Execute the agent's main logic.

        This is the core method that each agent must implement.
        It receives input and returns output.

        Returns:
            Agent-specific result
        """
        raise NotImplementedError

    # ================================================================
    # Harness Communication Helpers
    # ================================================================

    def send_message(
        self,
        receiver: str,
        message_type: str,
        payload: Dict[str, Any],
    ) -> Optional[Any]:
        """Send a message to another agent via the message bus.

        Args:
            receiver: Target agent ID
            message_type: Type of message (e.g., "request_assistance")
            payload: Message data

        Returns:
            Response message if in synchronous mode
        """
        if self.message_bus is None:
            return None

        from app.harness.message_bus import MessageType

        # Convert string to MessageType enum if needed
        if isinstance(message_type, str):
            message_type = MessageType(message_type)

        return self.message_bus.send_to(
            sender=self.agent_id,
            receiver=receiver,
            message_type=message_type,
            payload=payload,
        )

    def broadcast_message(
        self,
        message_type: str,
        payload: Dict[str, Any],
    ) -> int:
        """Broadcast a message to all agents.

        Args:
            message_type: Type of message
            payload: Message data

        Returns:
            Number of subscribers notified
        """
        if self.message_bus is None:
            return 0

        from app.harness.message_bus import MessageType

        if isinstance(message_type, str):
            message_type = MessageType(message_type)

        return self.message_bus.broadcast(
            sender=self.agent_id,
            message_type=message_type,
            payload=payload,
        )

    def write_to_blackboard(
        self,
        namespace: str,
        key: str,
        value: Any,
    ) -> int:
        """Write data to the shared blackboard.

        Args:
            namespace: Data grouping (e.g., "my_agent")
            key: Data identifier
            value: Data to store

        Returns:
            Version number
        """
        if self.blackboard is None:
            return 0
        return self.blackboard.write(namespace, key, value)

    def read_from_blackboard(
        self,
        namespace: str,
        key: Optional[str] = None,
    ) -> Any:
        """Read data from the shared blackboard.

        Args:
            namespace: Data grouping
            key: Specific key (None = read entire namespace)

        Returns:
            Stored data
        """
        if self.blackboard is None:
            return None
        return self.blackboard.read(namespace, key)

    def request_assistance(
        self,
        capability: str,
        payload: Dict[str, Any],
    ) -> Optional[Any]:
        """Request help from an agent with a specific capability.

        This demonstrates dynamic agent discovery and collaboration.

        Args:
            capability: What capability we need
            payload: Request data

        Returns:
            Response from the assisting agent
        """
        if self.harness is None:
            return None

        # Find agent with the capability
        agent_id = self.harness.registry.find_agent(capability)
        if agent_id is None:
            return None

        # Send request
        return self.send_message(
            receiver=agent_id,
            message_type="request_assistance",
            payload={
                **payload,
                "requesting_agent": self.agent_id,
                "capability_needed": capability,
            },
        )

    # ================================================================
    # Trace & Observability
    # ================================================================

    def _trace_step(
        self,
        step_type: str,
        detail: Dict[str, Any],
        thought: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> None:
        """Record a trace step for observability dashboard.

        Args:
            step_type: "thought", "action", "observation", "final"
            detail: What happened
            thought: Agent's reasoning
            session_id: Current session (uses "default" if not specified)
        """
        self._trace_collector.add_step(
            session_id=session_id or "default",
            agent_name=self.agent_id,
            step_type=step_type,
            detail=detail,
            thought=thought,
        )

    def get_status(self) -> Dict[str, Any]:
        """Get current agent status."""
        return {
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "version": self.version,
            "capabilities": self.capabilities,
            "dependencies": self.dependencies,
            "execution_count": self._execution_count,
            "last_input": str(self._last_input)[:100] if self._last_input else None,
            "last_output": str(self._last_output)[:100] if self._last_output else None,
            "last_error": self._last_error,
            "harness_connected": self.harness is not None,
        }

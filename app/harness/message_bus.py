"""MessageBus: Inter-agent communication system.

Provides a pub/sub message bus that allows agents to communicate without
direct dependencies. Messages can be:
- Broadcast to all agents (events)
- Sent to specific agents (direct messages)
- Request/response patterns (RPC-like)

This enables loose coupling and dynamic collaboration between agents.
"""

import time
import threading
import uuid
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
from collections import defaultdict


class MessageType(Enum):
    """Types of messages that can be sent between agents."""
    # System messages
    AGENT_STARTED = "agent_started"
    AGENT_COMPLETED = "agent_completed"
    AGENT_ERROR = "agent_error"

    # Data flow messages
    DATA_PARSED = "data_parsed"
    DATA_FEATURED = "data_featured"
    DATA_ANALYZED = "data_analyzed"
    DATA_RECOMMENDED = "data_recommended"

    # Collaboration messages
    REQUEST_ASSISTANCE = "request_assistance"
    RESPONSE_READY = "response_ready"
    QUERY_CONTEXT = "query_context"
    CONTEXT_PROVIDED = "context_provided"

    # Control messages
    PIPELINE_STEP_COMPLETED = "pipeline_step_completed"
    PIPELINE_PHASE_CHANGED = "pipeline_phase_changed"
    GOVERNANCE_ALERT = "governance_alert"


class Message:
    """A message passed between agents."""

    def __init__(
        self,
        message_type: MessageType,
        sender: str,
        payload: Dict[str, Any],
        receiver: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ):
        self.message_id = str(uuid.uuid4())
        self.message_type = message_type
        self.sender = sender
        self.receiver = receiver  # None = broadcast
        self.payload = payload
        self.correlation_id = correlation_id or str(uuid.uuid4())
        self.timestamp = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "message_id": self.message_id,
            "type": self.message_type.value,
            "sender": self.sender,
            "receiver": self.receiver,
            "payload": self.payload,
            "correlation_id": self.correlation_id,
            "timestamp": self.timestamp,
        }


class MessageBus:
    """Pub/sub message bus for inter-agent communication.

    Supports:
    - Direct messages (agent A -> agent B)
    - Broadcast messages (agent A -> all agents)
    - Message type subscriptions
    - Message history for debugging
    """

    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = defaultdict(list)
        self._type_subscribers: Dict[MessageType, List[Callable]] = defaultdict(list)
        self._history: List[Message] = []
        self._lock = threading.RLock()
        self._max_history = 1000

    def subscribe(self, agent_id: str, callback: Callable) -> None:
        """Subscribe to messages addressed to this agent.

        Args:
            agent_id: Unique identifier for the agent
            callback: Function to call when a message arrives
        """
        self._subscribers[agent_id].append(callback)

    def subscribe_type(self, message_type: MessageType, callback: Callable) -> None:
        """Subscribe to all messages of a specific type.

        Args:
            message_type: Type of messages to listen for
            callback: Function to call when matching message arrives
        """
        self._type_subscribers[message_type].append(callback)

    def send(self, message: Message) -> int:
        """Send a message through the bus.

        Args:
            message: The message to send

        Returns:
            Number of subscribers notified
        """
        with self._lock:
            # Store in history
            self._history.append(message)
            if len(self._history) > self._max_history:
                self._history.pop(0)

        notified = 0

        # Notify direct receiver
        if message.receiver and message.receiver in self._subscribers:
            for callback in self._subscribers[message.receiver]:
                try:
                    callback(message)
                    notified += 1
                except Exception:
                    pass

        # Notify type subscribers
        if message.message_type in self._type_subscribers:
            for callback in self._type_subscribers[message.message_type]:
                try:
                    callback(message)
                    notified += 1
                except Exception:
                    pass

        return notified

    def broadcast(self, sender: str, message_type: MessageType, payload: Dict[str, Any]) -> int:
        """Broadcast a message to all agents subscribed to this type.

        Args:
            sender: ID of the sending agent
            message_type: Type of message
            payload: Message data

        Returns:
            Number of subscribers notified
        """
        message = Message(
            message_type=message_type,
            sender=sender,
            payload=payload,
            receiver=None,  # Broadcast
        )
        return self.send(message)

    def send_to(self, sender: str, receiver: str, message_type: MessageType, payload: Dict[str, Any]) -> int:
        """Send a direct message to a specific agent.

        Args:
            sender: ID of the sending agent
            receiver: ID of the receiving agent
            message_type: Type of message
            payload: Message data

        Returns:
            Number of subscribers notified
        """
        message = Message(
            message_type=message_type,
            sender=sender,
            receiver=receiver,
            payload=payload,
        )
        return self.send(message)

    def request(self, sender: str, receiver: str, payload: Dict[str, Any]) -> Message:
        """Send a request and get response (synchronous pattern).

        Args:
            sender: ID of the requesting agent
            receiver: ID of the target agent
            payload: Request data

        Returns:
            Response message (or error if no response)
        """
        response_received = threading.Event()
        response_holder = [None]

        def response_callback(message: Message):
            if message.message_type == MessageType.RESPONSE_READY:
                response_holder[0] = message
                response_received.set()

        # Subscribe temporarily
        self._subscribers[sender].append(response_callback)

        # Send request
        self.send_to(
            sender=sender,
            receiver=receiver,
            message_type=MessageType.REQUEST_ASSISTANCE,
            payload=payload,
        )

        # Wait for response (with timeout consideration handled by caller)
        response_received.wait(timeout=30)

        # Cleanup subscription
        self._subscribers[sender].remove(response_callback)

        return response_holder[0]

    def get_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent message history for debugging.

        Args:
            limit: Maximum number of messages to return

        Returns:
            List of message dicts, newest first
        """
        with self._lock:
            return [m.to_dict() for m in reversed(self._history[-limit:])]

    def get_stats(self) -> Dict[str, Any]:
        """Get message bus statistics."""
        with self._lock:
            return {
                "total_messages": len(self._history),
                "subscribers": {
                    agent_id: len(callbacks)
                    for agent_id, callbacks in self._subscribers.items()
                },
                "type_subscribers": {
                    msg_type.value: len(callbacks)
                    for msg_type, callbacks in self._type_subscribers.items()
                },
            }

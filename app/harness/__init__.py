"""Harness: Multi-Agent Orchestration Framework.

Provides the core infrastructure for building production-grade multi-agent systems:
- Blackboard: Shared state and data exchange
- MessageBus: Inter-agent communication
- AgentRegistry: Agent lifecycle management
- Governance: Rules, budgets, and safety constraints
- Harness: Central orchestrator that ties everything together
"""

from app.harness.blackboard import Blackboard
from app.harness.message_bus import MessageBus, Message, MessageType
from app.harness.agent_registry import AgentRegistry, AgentDescriptor
from app.harness.governance import GovernanceEngine, GovernanceRule, BudgetTracker
from app.harness.harness import Harness

__all__ = [
    "Blackboard",
    "MessageBus",
    "Message",
    "MessageType",
    "AgentRegistry",
    "AgentDescriptor",
    "GovernanceEngine",
    "GovernanceRule",
    "BudgetTracker",
    "Harness",
]

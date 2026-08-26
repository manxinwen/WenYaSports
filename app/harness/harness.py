"""Harness: Central orchestrator for multi-agent systems.

The Harness is the heart of the multi-agent architecture. It provides:
1. Agent lifecycle management (via AgentRegistry)
2. Inter-agent communication (via MessageBus)
3. Shared state management (via Blackboard)
4. Governance and safety (via GovernanceEngine)
5. Dynamic orchestration and workflow execution

Architecture:
                    ┌─────────────────────────────────────────┐
                    │            HARNESS                     │
                    │  ┌─────────────────────────────────┐  │
                    │  │  AgentRegistry  │  MessageBus    │  │
                    │  └─────────────────────────────────┘  │
                    │  ┌─────────────────────────────────┐  │
                    │  │  Blackboard     │ GovernanceEngine│ │
                    │  └─────────────────────────────────┘  │
                    └─────────────────────────────────────────┘
                                      │
                    ┌─────────────────┼─────────────────┐
                    ▼                 ▼                 ▼
              ┌──────────┐      ┌──────────┐      ┌──────────┐
              │ Agent A  │      │ Agent B  │      │ Agent C  │
              └──────────┘      └──────────┘      └──────────┘
"""

import time
import uuid
import logging
from typing import Any, Callable, Dict, List, Optional
from collections import defaultdict

from app.harness.blackboard import Blackboard
from app.harness.message_bus import MessageBus, Message, MessageType
from app.harness.agent_registry import AgentRegistry, AgentDescriptor, AgentStatus
from app.harness.governance import GovernanceEngine, BudgetTracker
from app.trace import trace_collector

logger = logging.getLogger(__name__)


class Harness:
    """Central orchestrator for multi-agent systems.

    The Harness wraps all agents in a controlled execution environment,
    providing lifecycle management, communication, state sharing,
    and governance capabilities.

    Usage:
        harness = Harness()
        harness.register_agent(parser_instance, "parser", ...)
        harness.register_agent(memory_instance, "memory", ...)

        # Execute a workflow
        result = harness.run_workflow("pipeline", input_data)
    """

    def __init__(self):
        # Core infrastructure
        self.blackboard = Blackboard()
        self.message_bus = MessageBus()
        self.registry = AgentRegistry()
        self.governance = GovernanceEngine()

        # Execution tracking
        self._session_id: Optional[str] = None
        self._workflow_history: List[Dict[str, Any]] = []
        self._current_phase: Optional[str] = None

        # Event callbacks
        self._on_agent_started: Optional[Callable] = None
        self._on_agent_completed: Optional[Callable] = None
        self._on_phase_changed: Optional[Callable] = None

        # Set up message bus integration
        self._setup_message_handlers()

    def _setup_message_handlers(self):
        """Set up internal message bus handlers."""
        # Subscribe to completion events to enable chaining
        self.message_bus.subscribe_type(
            MessageType.AGENT_COMPLETED,
            self._handle_agent_completed,
        )
        self.message_bus.subscribe_type(
            MessageType.GOVERNANCE_ALERT,
            self._handle_governance_alert,
        )

    def _handle_agent_completed(self, message: Message):
        """Handle agent completion - triggers chaining logic."""
        agent_id = message.sender
        result = message.payload
        if self._on_agent_completed:
            self._on_agent_completed(agent_id, result)

    def _handle_governance_alert(self, message: Message):
        """Handle governance alerts."""
        logger.warning(f"Governance alert: {message.payload}")

    # ================================================================
    # Agent Registration
    # ================================================================

    def register_agent(
        self,
        agent_instance: Any,
        agent_id: str,
        name: str,
        capabilities: List[str],
        version: str = "1.0.0",
        dependencies: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        budget: Optional[BudgetTracker] = None,
    ) -> AgentDescriptor:
        """Register an agent with the harness.

        Args:
            agent_instance: The actual agent object
            agent_id: Unique identifier
            name: Human-readable name
            capabilities: What this agent provides
            version: Agent version
            dependencies: Required agent capabilities
            metadata: Additional info
            budget: Resource budget for this agent

        Returns:
            AgentDescriptor for the registered agent
        """
        descriptor = self.registry.register(
            agent_id=agent_id,
            agent_instance=agent_instance,
            name=name,
            capabilities=capabilities,
            version=version,
            dependencies=dependencies,
            metadata=metadata,
        )

        # Set budget if provided
        if budget:
            self.governance.set_budget(agent_id, budget)
        else:
            self.governance.set_budget(agent_id, BudgetTracker())

        # Set up message subscription for the agent
        self.message_bus.subscribe(
            agent_id,
            lambda msg: self._route_to_agent(agent_id, msg),
        )

        # Initialize agent's harness reference
        if hasattr(agent_instance, "harness"):
            agent_instance.harness = self
        if hasattr(agent_instance, "blackboard"):
            agent_instance.blackboard = self.blackboard
        if hasattr(agent_instance, "message_bus"):
            agent_instance.message_bus = self.message_bus

        logger.info(f"Agent '{agent_id}' registered with capabilities: {capabilities}")
        return descriptor

    def deregister_agent(self, agent_id: str) -> bool:
        """Remove an agent from the harness."""
        return self.registry.deregister(agent_id)

    # ================================================================
    # Agent Execution
    # ================================================================

    def execute_agent(
        self,
        agent_id: str,
        *args: Any,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Execute a single agent with governance and tracing.

        Args:
            agent_id: ID of the agent to execute
            *args, **kwargs: Arguments passed to agent.run()

        Returns:
            Execution result dict
        """
        agent_instance = self.registry.get_instance(agent_id)
        descriptor = self.registry.get_descriptor(agent_id)

        if agent_instance is None:
            return {"success": False, "error": f"Agent '{agent_id}' not found"}

        # Mark as running
        self.registry.set_status(agent_id, AgentStatus.RUNNING)
        trace_collector.add_step(
            session_id=self._session_id or "default",
            agent_name=agent_id,
            step_type="thought",
            detail={"action": "start_execution", "args": str(args)},
            thought=f"Executing agent: {agent_id}",
        )

        # Send started message
        self.message_bus.broadcast(
            sender="harness",
            message_type=MessageType.AGENT_STARTED,
            payload={"agent_id": agent_id, "session_id": self._session_id},
        )

        # Execute with governance
        def execute_fn():
            return agent_instance.run(*args, **kwargs)

        result = self.governance.execute_with_governance(
            agent_id=agent_id,
            execution_fn=execute_fn,
            context={
                "agent_id": agent_id,
                "tokens_used": kwargs.get("estimated_tokens", 0),
                "execution_time_ms": 0,
            },
        )

        # Update state based on result
        if result.get("success"):
            self.registry.set_status(agent_id, AgentStatus.IDLE)
            self.registry.increment_execution(agent_id)

            trace_collector.add_step(
                session_id=self._session_id or "default",
                agent_name=agent_id,
                step_type="final",
                detail={"result": str(result.get("result", ""))[:200]},
                thought=f"Agent {agent_id} completed successfully",
            )

            self.message_bus.broadcast(
                sender="harness",
                message_type=MessageType.AGENT_COMPLETED,
                payload={
                    "agent_id": agent_id,
                    "result": result.get("result"),
                    "session_id": self._session_id,
                },
            )
        else:
            self.registry.set_status(agent_id, AgentStatus.ERROR)
            trace_collector.add_step(
                session_id=self._session_id or "default",
                agent_name=agent_id,
                step_type="final",
                detail={"error": result.get("error", "blocked")},
                thought=f"Agent {agent_id} failed: {result.get('error', 'unknown')}",
            )

            self.message_bus.broadcast(
                sender="harness",
                message_type=MessageType.AGENT_ERROR,
                payload={
                    "agent_id": agent_id,
                    "error": result.get("error", "unknown"),
                    "session_id": self._session_id,
                },
            )

        return result

    # ================================================================
    # Workflow Execution
    # ================================================================

    def run_workflow(
        self,
        workflow_name: str,
        steps: List[Dict[str, Any]],
        initial_input: Any,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute a multi-agent workflow.

        Args:
            workflow_name: Name for this workflow execution
            steps: Ordered list of workflow steps
                Each step: {"agent_id": "...", "input_key": "...", "output_key": "..."}
            initial_input: Input data for the first step
            session_id: Optional session ID for tracing

        Returns:
            Final result with intermediate outputs
        """
        self._session_id = session_id or str(uuid.uuid4())
        results = {}
        current_input = initial_input

        trace_collector.record_session_start(
            session_id=self._session_id,
            user_request=workflow_name,
        )

        trace_collector.add_step(
            session_id=self._session_id,
            agent_name="harness",
            step_type="thought",
            detail={"workflow": workflow_name, "steps": len(steps)},
            thought=f"Starting workflow: {workflow_name} with {len(steps)} steps",
        )

        for i, step in enumerate(steps):
            agent_id = step["agent_id"]
            input_key = step.get("input_key")
            output_key = step.get("output_key", f"step_{i}_output")

            # Get input for this step
            if input_key:
                step_input = results.get(input_key, current_input)
            else:
                step_input = current_input

            self._current_phase = f"step_{i}_{agent_id}"

            trace_collector.add_step(
                session_id=self._session_id,
                agent_name="harness",
                step_type="action",
                detail={
                    "step_index": i,
                    "agent_id": agent_id,
                    "phase": self._current_phase,
                },
                thought=f"Step {i+1}/{len(steps)}: Delegating to {agent_id}",
            )

            # Execute agent
            result = self.execute_agent(agent_id, step_input)

            if not result.get("success"):
                error = result.get("error", "Unknown error")
                trace_collector.add_step(
                    session_id=self._session_id,
                    agent_name="harness",
                    step_type="final",
                    detail={"error": error, "step": i},
                    thought=f"Workflow failed at step {i+1}: {error}",
                )
                trace_collector.record_session_end(
                    session_id=self._session_id,
                    success=False,
                    total_steps=i + 1,
                )
                return {
                    "success": False,
                    "workflow": workflow_name,
                    "error": error,
                    "completed_steps": i,
                    "results": results,
                }

            # Store result
            results[output_key] = result.get("result")
            current_input = result.get("result")

            # Write to blackboard
            self.blackboard.write(
                namespace=f"workflow_{workflow_name}",
                key=output_key,
                value=result.get("result"),
            )

        # Workflow completed
        trace_collector.add_step(
            session_id=self._session_id,
            agent_name="harness",
            step_type="final",
            detail={"total_steps": len(steps)},
            thought=f"Workflow '{workflow_name}' completed successfully",
        )
        trace_collector.record_session_end(
            session_id=self._session_id,
            success=True,
            total_steps=len(steps),
        )

        # Record in history
        self._workflow_history.append({
            "workflow": workflow_name,
            "session_id": self._session_id,
            "steps_completed": len(steps),
            "success": True,
            "timestamp": time.time(),
        })

        return {
            "success": True,
            "workflow": workflow_name,
            "session_id": self._session_id,
            "results": results,
            "final_output": current_input,
            "steps_completed": len(steps),
        }

    # ================================================================
    # Dynamic Orchestration
    # ================================================================

    def orchestrate(
        self,
        goal: str,
        initial_input: Any,
        max_iterations: int = 10,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Dynamically orchestrate agents to achieve a goal.

        Unlike run_workflow (which follows a fixed plan), orchestrate
        allows agents to discover each other and collaborate dynamically.

        Args:
            goal: What we're trying to achieve
            initial_input: Starting data
            max_iterations: Maximum agent iterations
            session_id: Optional session ID

        Returns:
            Final result
        """
        self._session_id = session_id or str(uuid.uuid4())
        trace_collector.record_session_start(
            session_id=self._session_id,
            user_request=goal,
        )

        # Write initial context to blackboard
        self.blackboard.write("context", "goal", goal)
        self.blackboard.write("context", "input", initial_input)
        self.blackboard.write("context", "iteration", 0)

        current_input = initial_input
        iterations = 0
        history = []

        trace_collector.add_step(
            session_id=self._session_id,
            agent_name="harness",
            step_type="thought",
            detail={"goal": goal},
            thought=f"Starting dynamic orchestration for goal: {goal}",
        )

        while iterations < max_iterations:
            iterations += 1
            self.blackboard.write("context", "iteration", iterations)

            # Find best agent for current task
            best_agent = self._select_next_agent(goal, current_input, history)

            if best_agent is None:
                trace_collector.add_step(
                    session_id=self._session_id,
                    agent_name="harness",
                    step_type="final",
                    detail={"iterations": iterations},
                    thought=f"No more agents needed after {iterations} iterations",
                )
                break

            trace_collector.add_step(
                session_id=self._session_id,
                agent_name="harness",
                step_type="action",
                detail={"selected_agent": best_agent, "iteration": iterations},
                thought=f"Iteration {iterations}: Selected {best_agent} for task",
            )

            # Execute selected agent
            result = self.execute_agent(best_agent, current_input)

            if result.get("success"):
                current_input = result.get("result")
                history.append({
                    "agent": best_agent,
                    "result": current_input,
                    "iteration": iterations,
                })

                # Write to blackboard
                self.blackboard.write("context", "last_result", current_input)
                self.blackboard.write("context", "last_agent", best_agent)
            else:
                trace_collector.add_step(
                    session_id=self._session_id,
                    agent_name="harness",
                    step_type="observation",
                    detail={"error": result.get("error")},
                    thought=f"Agent {best_agent} failed: {result.get('error')}",
                )

                # Try fallback
                fallback_agent = self._find_fallback_agent(best_agent)
                if fallback_agent:
                    trace_collector.add_step(
                        session_id=self._session_id,
                        agent_name="harness",
                        step_type="action",
                        detail={"fallback_agent": fallback_agent},
                        thought=f"Trying fallback agent: {fallback_agent}",
                    )
                    result = self.execute_agent(fallback_agent, current_input)
                    if result.get("success"):
                        current_input = result.get("result")
                        history.append({
                            "agent": fallback_agent,
                            "result": current_input,
                            "iteration": iterations,
                            "fallback": True,
                        })
                else:
                    break
            pass

        trace_collector.add_step(
            session_id=self._session_id,
            agent_name="harness",
            step_type="final",
            detail={"total_iterations": iterations},
            thought=f"Orchestration completed after {iterations} iterations",
        )
        trace_collector.record_session_end(
            session_id=self._session_id,
            success=True,
            total_steps=iterations,
        )

        return {
            "success": True,
            "goal": goal,
            "session_id": self._session_id,
            "iterations": iterations,
            "history": history,
            "final_result": current_input,
        }

    def _select_next_agent(
        self,
        goal: str,
        current_input: Any,
        history: List[Dict],
    ) -> Optional[str]:
        """Select the best agent for the next step.

        Uses capability matching and state-based selection.
        """
        # Get all available agents
        available_agents = self.registry.list_agents()

        # Simple selection heuristic:
        # 1. Find agents whose capabilities match the goal
        # 2. Prefer agents that haven't been used recently
        # 3. Consider the current state of the blackboard

        candidates = []
        for agent in available_agents:
            agent_id = agent["agent_id"]
            agent_status = agent["status"]

            if agent_status not in ("idle", "running"):
                continue

            # Check if agent was already used in recent history
            recent_use = any(
                h["agent"] == agent_id
                for h in history[-3:]  # Last 3 iterations
            )

            if not recent_use:
                candidates.append(agent_id)

        if candidates:
            return candidates[0]
        elif available_agents:
            return available_agents[0]["agent_id"]
        return None

    def _find_fallback_agent(self, failed_agent_id: str) -> Optional[str]:
        """Find a fallback agent with similar capabilities."""
        descriptor = self.registry.get_descriptor(failed_agent_id)
        if descriptor is None:
            return None

        # Find other agents with overlapping capabilities
        for cap in descriptor.capabilities:
            alternatives = self.registry.get_by_capability(cap)
            for alt_id in alternatives:
                if alt_id != failed_agent_id:
                    alt_desc = self.registry.get_descriptor(alt_id)
                    if alt_desc and alt_desc.status == AgentStatus.IDLE:
                        return alt_id
        return None

    # ================================================================
    # Utility Methods
    # ================================================================

    def get_system_status(self) -> Dict[str, Any]:
        """Get complete system status for dashboard."""
        return {
            "agents": self.registry.get_stats(),
            "message_bus": self.message_bus.get_stats(),
            "blackboard": self.blackboard.get_stats(),
            "governance": self.governance.get_stats(),
            "workflow_history": self._workflow_history[-10:],
            "current_phase": self._current_phase,
            "active_session": self._session_id,
        }

    def get_agent_status(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a specific agent."""
        descriptor = self.registry.get_descriptor(agent_id)
        if descriptor:
            return descriptor.to_dict()
        return None

    def reset_session(self) -> None:
        """Reset the current session state."""
        self._session_id = None
        self._current_phase = None

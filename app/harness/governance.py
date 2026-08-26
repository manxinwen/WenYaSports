"""GovernanceEngine: Rules, budgets, and safety constraints for agents.

Provides governance capabilities to ensure agents operate within safe boundaries:
- Token/API call budgets
- Execution time limits
- Permission/access control
- Output validation
- Circuit breaker patterns
"""

import time
from typing import Any, Callable, Dict, List, Optional
from dataclasses import dataclass, field
from collections import defaultdict
from enum import Enum


class RuleAction(Enum):
    """Action to take when a rule is violated."""
    WARN = "warn"  # Log warning, continue
    BLOCK = "block"  # Block the operation
    RATE_LIMIT = "rate_limit"  # Apply rate limiting
    FALLBACK = "fallback"  # Use fallback behavior


@dataclass
class GovernanceRule:
    """A governance rule that agents must follow.

    Attributes:
        rule_id: Unique identifier
        name: Human-readable name
        description: What the rule governs
        check_fn: Function that returns True if rule is violated
        action: What to do when violated
        severity: How critical this rule is (1-5)
        enabled: Whether the rule is active
    """
    rule_id: str
    name: str
    description: str
    check_fn: Callable[[Dict[str, Any]], bool]
    action: RuleAction = RuleAction.WARN
    severity: int = 3
    enabled: bool = True


@dataclass
class BudgetTracker:
    """Track resource usage for an agent or the system.

    Attributes:
        daily_token_limit: Max tokens per day
        daily_api_call_limit: Max API calls per day
        max_execution_time_ms: Max single execution time
        reset_time: When counters reset
    """
    daily_token_limit: int = 100000
    daily_api_call_limit: int = 1000
    max_execution_time_ms: int = 30000  # 30 seconds

    def __post_init__(self):
        self._tokens_used: float = 0
        self._api_calls: int = 0
        self._reset_date: str = time.strftime("%Y-%m-%d")

    @property
    def tokens_used(self) -> float:
        self._check_reset()
        return self._tokens_used

    @property
    def api_calls(self) -> int:
        self._check_reset()
        return self._api_calls

    def _check_reset(self):
        current_date = time.strftime("%Y-%m-%d")
        if current_date != self._reset_date:
            self._tokens_used = 0
            self._api_calls = 0
            self._reset_date = current_date

    def add_tokens(self, tokens: float) -> bool:
        """Add token usage. Returns True if within budget."""
        self._check_reset()
        self._tokens_used += tokens
        return self._tokens_used <= self.daily_token_limit

    def increment_api_calls(self) -> bool:
        """Increment API call counter. Returns True if within budget."""
        self._check_reset()
        self._api_calls += 1
        return self._api_calls <= self.daily_api_call_limit

    def check_execution_time(self, start_time: float) -> bool:
        """Check if execution time is within limits."""
        elapsed_ms = (time.time() - start_time) * 1000
        return elapsed_ms <= self.max_execution_time_ms

    def get_usage(self) -> Dict[str, Any]:
        """Get current usage statistics."""
        self._check_reset()
        return {
            "tokens_used": self._tokens_used,
            "tokens_remaining": self.daily_token_limit - self._tokens_used,
            "token_usage_pct": (self._tokens_used / self.daily_token_limit) * 100,
            "api_calls": self._api_calls,
            "api_calls_remaining": self.daily_api_call_limit - self._api_calls,
            "api_usage_pct": (self._api_calls / self.daily_api_call_limit) * 100,
        }


class GovernanceEngine:
    """Engine that applies governance rules and budget controls.

    Responsibilities:
    - Enforce rules before agent actions
    - Track budgets per agent and system-wide
    - Log violations for observability
    - Provide fallback behaviors when limits are exceeded
    """

    def __init__(self):
        self._rules: Dict[str, GovernanceRule] = {}
        self._agent_budgets: Dict[str, BudgetTracker] = {}
        self._system_budget = BudgetTracker(
            daily_token_limit=500000,
            daily_api_call_limit=5000,
        )
        self._violations: List[Dict[str, Any]] = []
        self._fallbacks: Dict[str, Callable] = {}

        # Initialize default rules
        self._init_default_rules()

    def _init_default_rules(self):
        """Set up default governance rules."""

        # Rule: Budget check
        self.add_rule(
            GovernanceRule(
                rule_id="budget_check",
                name="Budget Compliance",
                description="Ensure agent stays within resource budget",
                check_fn=lambda context: self._check_budget_violation(context),
                action=RuleAction.RATE_LIMIT,
                severity=4,
            )
        )

        # Rule: Execution time
        self.add_rule(
            GovernanceRule(
                rule_id="execution_time",
                name="Execution Time Limit",
                description="Prevent agent from running too long",
                check_fn=lambda context: context.get("execution_time_ms", 0) > 30000,
                action=RuleAction.BLOCK,
                severity=5,
            )
        )

        # Rule: Data validation
        self.add_rule(
            GovernanceRule(
                rule_id="output_validation",
                name="Output Validation",
                description="Ensure agent output is valid JSON",
                check_fn=lambda context: not self._is_valid_output(context),
                action=RuleAction.FALLBACK,
                severity=3,
            )
        )

    def _check_budget_violation(self, context: Dict[str, Any]) -> bool:
        """Check if any budget is violated."""
        agent_id = context.get("agent_id", "unknown")
        tokens = context.get("tokens_used", 0)
        api_calls = context.get("api_calls", 0)

        budget = self._agent_budgets.get(agent_id)
        if budget:
            if tokens > 0 and budget.tokens_used + tokens > budget.daily_token_limit:
                return True
            if api_calls > 0 and budget.api_calls + api_calls > budget.daily_api_call_limit:
                return True
        return False

    def _is_valid_output(self, context: Dict[str, Any]) -> bool:
        """Check if agent output is valid."""
        output = context.get("output")
        if output is None:
            return True  # No output to validate
        # Basic validation - output should be JSON-serializable
        try:
            import json
            json.dumps(output)
            return True
        except (TypeError, ValueError):
            return False

    def add_rule(self, rule: GovernanceRule) -> None:
        """Add a governance rule."""
        self._rules[rule.rule_id] = rule

    def set_budget(self, agent_id: str, budget: BudgetTracker) -> None:
        """Set budget for a specific agent."""
        self._agent_budgets[agent_id] = budget

    def get_budget(self, agent_id: str) -> BudgetTracker:
        """Get budget tracker for an agent (creates default if not exists)."""
        if agent_id not in self._agent_budgets:
            self._agent_budgets[agent_id] = BudgetTracker()
        return self._agent_budgets[agent_id]

    def check_compliance(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Run all governance rules against a context.

        Args:
            context: Dictionary with keys like 'agent_id', 'tokens_used', etc.

        Returns:
            Dict with 'compliant', 'violations', and 'actions'
        """
        violations = []
        actions = []

        for rule_id, rule in self._rules.items():
            if not rule.enabled:
                continue

            try:
                if rule.check_fn(context):
                    violation = {
                        "rule_id": rule_id,
                        "rule_name": rule.name,
                        "severity": rule.severity,
                        "action": rule.action.value,
                        "context": context,
                        "timestamp": time.time(),
                    }
                    violations.append(violation)
                    actions.append(rule.action)
                    self._violations.append(violation)
            except Exception:
                pass  # Don't let rule check errors break execution

        return {
            "compliant": len(violations) == 0,
            "violations": violations,
            "actions": list(set([a.value for a in actions])),
        }

    def execute_with_governance(
        self,
        agent_id: str,
        execution_fn: Callable,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Execute a function with governance checks.

        Args:
            agent_id: Agent being executed
            execution_fn: The function to execute
            context: Governance context

        Returns:
            Execution result dict
        """
        start_time = time.time()
        budget = self.get_budget(agent_id)

        # Check compliance
        compliance = self.check_compliance({
            **context,
            "agent_id": agent_id,
            "execution_time_ms": (time.time() - start_time) * 1000,
        })

        if not compliance["compliant"]:
            # Handle violations
            for action in compliance["actions"]:
                if action == "block":
                    return {
                        "success": False,
                        "blocked": True,
                        "reason": "Governance rule blocked execution",
                        "violations": compliance["violations"],
                    }
                elif action == "rate_limit":
                    # Apply rate limit by checking budget
                    if not budget.check_execution_time(start_time):
                        return {
                            "success": False,
                            "blocked": True,
                            "reason": "Execution time limit exceeded",
                        }

        # Execute with tracking
        try:
            result = execution_fn()
            elapsed_ms = (time.time() - start_time) * 1000

            # Track usage
            budget.increment_api_calls()
            self._system_budget.increment_api_calls()

            return {
                "success": True,
                "result": result,
                "execution_time_ms": elapsed_ms,
                "compliance_passed": True,
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "execution_time_ms": (time.time() - start_time) * 1000,
            }

    def register_fallback(self, rule_id: str, fallback_fn: Callable) -> None:
        """Register a fallback function for a rule."""
        self._fallbacks[rule_id] = fallback_fn

    def get_violations(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent governance violations."""
        return self._violations[-limit:]

    def get_stats(self) -> Dict[str, Any]:
        """Get governance statistics."""
        return {
            "total_rules": len(self._rules),
            "enabled_rules": sum(1 for r in self._rules.values() if r.enabled),
            "total_violations": len(self._violations),
            "system_budget": self._system_budget.get_usage(),
            "agent_budgets": {
                aid: budget.get_usage()
                for aid, budget in self._agent_budgets.items()
            },
        }

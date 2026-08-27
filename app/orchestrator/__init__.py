"""LLM-Driven Orchestrator: 智能多Agent编排引擎。

核心设计：
- LLM 作为「智能项目经理」，分析目标、规划步骤、动态编排 Agent
- 支持能力匹配、故障重规划、多策略降级
- 完整的可观测性追踪
- Planner-Executor-Reviser 多角色对话协作

Architecture:
    User Request
        ↓
    ┌──────────────────────┐
    │  LLMOrchestrator     │
    │  - Intent Analysis   │
    │  - Plan Generation   │
    │  - Dynamic Routing   │
    │  - Re-planning       │
    └──────────────────────┘
        ↓         ↓         ↓
    Agent A    Agent B    Agent C

    Conversation Mode:
    User → Planner → Executor → Reviser → [Iterate] → Final Answer
"""

from app.orchestrator.llm_orchestrator import LLMOrchestrator
from app.orchestrator.plan_parser import PlanStep, ExecutionPlan
from app.orchestrator.conversation import (
    ConversationOrchestrator,
    ConversationState,
    ConversationMessage,
)

__all__ = [
    "LLMOrchestrator",
    "PlanStep",
    "ExecutionPlan",
    "ConversationOrchestrator",
    "ConversationState",
    "ConversationMessage",
]
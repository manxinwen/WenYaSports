"""LLM-Driven Orchestrator: 智能多Agent编排引擎。

核心设计：
- LLM 作为「智能项目经理」，分析目标、规划步骤、动态编排 Agent
- 支持能力匹配、故障重规划、多策略降级
- 完整的可观测性追踪
- Planner-Executor-Reviser 多角色对话协作
- Agentic Workflow: 自主思考、动态选工具、反思循环
- 三层决策架构: 战略/战术/验证
- Agent 协商协议: 多 Agent 协作冲突解决
- 决策可解释层: 所有决策透明可追溯

Architecture:
    User Request
        ↓
    ┌──────────────────────────────────┐
    │   AgenticWorkflowEngine          │
    │   ┌──────────────────────────┐   │
    │   │  DecisionEngine (LLM)    │   │
    │   │  - Strategic Decision    │   │
    │   │  - Tactical Decision     │   │
    │   │  - Validation (Critique) │   │
    │   └──────────────────────────┘   │
    │   ┌──────────────────────────┐   │
    │   │  Execution Engine        │   │
    │   │  - Tool Chain            │   │
    │   │  - Error Recovery        │   │
    │   │  - Result Fusion         │   │
    │   └──────────────────────────┘   │
    └──────────────────────────────────┘
        ↓         ↓         ↓
    Agent A    Agent B    MCP Tools

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
from app.orchestrator.agentic_workflow import (
    AgenticWorkflowEngine,
    WorkflowState,
    WorkflowStatus,
    ToolCall,
    ThoughtNode,
)
from app.orchestrator.decision_engine import (
    LLMDecisionEngine,
    DecisionResult,
    CritiqueResult,
    DebateResult,
    DecisionLayer,
    DecisionType,
)
from app.orchestrator.negotiation import (
    NegotiationSession,
    NegotiationType,
    NegotiationStatus,
    NegotiationResult,
    NegotiationRound,
    AgentProposal,
    VoteRecord,
    ProposalRank,
    quick_delegate,
    resolve_capability_dispute,
)
from app.orchestrator.explainability import (
    ExplainabilityEngine,
    ExplainabilityType,
    DecisionRecord,
    Explanation,
    DecisionPath,
)

__all__ = [
    # Legacy orchestrator
    "LLMOrchestrator",
    "PlanStep",
    "ExecutionPlan",
    # Conversation mode
    "ConversationOrchestrator",
    "ConversationState",
    "ConversationMessage",
    # Agentic workflow
    "AgenticWorkflowEngine",
    "WorkflowState",
    "WorkflowStatus",
    "ToolCall",
    "ThoughtNode",
    # Decision engine
    "LLMDecisionEngine",
    "DecisionResult",
    "CritiqueResult",
    "DebateResult",
    "DecisionLayer",
    "DecisionType",
    # Negotiation protocol
    "NegotiationSession",
    "NegotiationType",
    "NegotiationStatus",
    "NegotiationResult",
    "NegotiationRound",
    "AgentProposal",
    "VoteRecord",
    "ProposalRank",
    "quick_delegate",
    "resolve_capability_dispute",
    # Explainability
    "ExplainabilityEngine",
    "ExplainabilityType",
    "DecisionRecord",
    "Explanation",
    "DecisionPath",
]
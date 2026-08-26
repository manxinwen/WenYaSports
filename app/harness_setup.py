"""Harness setup and API integration.

This module initializes the Harness with all agents and provides
API endpoints for dashboard monitoring and dynamic orchestration.
"""

import logging
from typing import Any, Dict, List, Optional

from app.harness import (
    Harness,
    Blackboard,
    MessageBus,
    AgentRegistry,
    GovernanceEngine,
    BudgetTracker,
    MessageType,
)

logger = logging.getLogger(__name__)

# Global harness instance
_harness: Optional[Harness] = None


def get_harness() -> Harness:
    """Get or create the global Harness instance.

    This follows the singleton pattern used for the coordinator.
    """
    global _harness
    if _harness is None:
        _harness = create_harness()
    return _harness


def create_harness() -> Harness:
    """Create and configure the Harness with all agents.

    This is where we:
    1. Create the Harness orchestrator
    2. Register all agents with their capabilities
    3. Set up budgets and governance rules
    4. Configure inter-agent communication

    Returns:
        Configured Harness instance
    """
    from app.agents.parser_agent import ParserAgent
    from app.agents.feature_extractor_agent import FeatureExtractorAgent
    from app.agents.memory_agent import MemoryAgent
    from app.agents.recommendation_agent import RecommendationAgent
    from app.agents.reaact_agent import ReActAgent
    from mcp_plugins import PluginManager

    harness = Harness()

    # ================================================================
    # Agent Definitions with Capabilities
    # ================================================================

    # 1. ParserAgent - Expert at FIT file parsing
    parser = ParserAgent()
    harness.register_agent(
        agent_instance=parser,
        agent_id="parser",
        name="FIT Parser",
        capabilities=["fit_parsing", "data_extraction", "metadata_parsing"],
        version="1.0.0",
        dependencies=[],
        metadata={
            "description": "Specializes in parsing Garmin FIT files",
            "input_types": [".fit", ".fit.gz"],
            "output_types": ["ParsedActivity"],
        },
        budget=BudgetTracker(
            daily_token_limit=10000,
            daily_api_call_limit=100,
        ),
    )

    # 2. FeatureExtractorAgent - Expert at feature engineering
    feature_extractor = FeatureExtractorAgent()
    harness.register_agent(
        agent_instance=feature_extractor,
        agent_id="feature_extractor",
        name="Feature Extractor",
        capabilities=["feature_engineering", "statistics", "intensity_distribution"],
        version="1.0.0",
        dependencies=["fit_parsing"],
        metadata={
            "description": "Extracts training metrics and statistics",
            "computes": ["distance", "duration", "elevation", "heart_rate_zones"],
        },
        budget=BudgetTracker(
            daily_token_limit=10000,
            daily_api_call_limit=100,
        ),
    )

    # 3. MemoryAgent - Expert at user profile management
    memory = MemoryAgent()
    harness.register_agent(
        agent_instance=memory,
        agent_id="memory",
        name="Memory Manager",
        capabilities=["user_profile", "context_retrieval", "memory_update"],
        version="1.0.0",
        dependencies=[],
        metadata={
            "description": "Manages user profiles and training history",
            "storage": "SQLite + Vector DB",
        },
        budget=BudgetTracker(
            daily_token_limit=20000,
            daily_api_call_limit=200,
        ),
    )

    # 4. RecommendationAgent - Expert at training advice
    recommender = RecommendationAgent()
    harness.register_agent(
        agent_instance=recommender,
        agent_id="recommender",
        name="Recommendation Engine",
        capabilities=["training_advice", "rule_engine", "llm_generation"],
        version="1.0.0",
        dependencies=["feature_engineering", "user_profile"],
        metadata={
            "description": "Generates personalized training recommendations",
            "methods": ["rules", "llm", "hybrid"],
        },
        budget=BudgetTracker(
            daily_token_limit=50000,
            daily_api_call_limit=500,
        ),
    )

    # 5. ReActAgent - Expert at tool-using and reasoning
    plugin_manager = PluginManager()
    react = ReActAgent(plugin_manager=plugin_manager)
    harness.register_agent(
        agent_instance=react,
        agent_id="react",
        name="ReAct Agent",
        capabilities=["tool_calling", "reasoning", "multi_step_planning"],
        version="1.0.0",
        dependencies=["memory_update", "training_advice"],
        metadata={
            "description": "ReAct pattern agent for complex queries",
            "tools_available": plugin_manager.get_all_tools(),
        },
        budget=BudgetTracker(
            daily_token_limit=50000,
            daily_api_call_limit=500,
        ),
    )

    # ================================================================
    # Configure Agent Communication
    # ================================================================

    # Set up message routing - agents can request assistance
    harness.message_bus.subscribe(
        "memory",
        lambda msg: logger.debug(f"Memory received: {msg.message_type.value}"),
    )
    harness.message_bus.subscribe(
        "recommender",
        lambda msg: logger.debug(f"Recommender received: {msg.message_type.value}"),
    )

    # ================================================================
    # Initialize Blackboard with System Info
    # ================================================================

    harness.blackboard.write(
        "system",
        "config",
        {
            "harness_version": "2.0.0",
            "architecture": "Multi-Agent Harness",
            "design_pattern": "Orchestration + Blackboard + Message Bus",
            "total_agents": len(harness.registry.list_agents()),
            "capabilities": harness.registry.get_available_capabilities(),
        },
    )

    harness.blackboard.write(
        "system",
        "initialized_at",
        __import__("time").time(),
    )

    logger.info(f"Harness initialized with {len(harness.registry.list_agents())} agents")
    return harness


# ================================================================
# Predefined Workflows
# ================================================================

def get_analysis_workflow() -> List[Dict[str, Any]]:
    """Get the standard activity analysis workflow.

    This workflow demonstrates the Harness orchestrating multiple agents:
    1. ParserAgent → Parse FIT file
    2. FeatureExtractorAgent → Extract metrics
    3. MemoryAgent → Load user context
    4. RecommendationAgent → Generate advice
    5. MemoryAgent → Update user profile
    """
    return [
        {
            "agent_id": "parser",
            "input_key": "file_path",
            "output_key": "parsed_activity",
        },
        {
            "agent_id": "feature_extractor",
            "input_key": "parsed_activity",
            "output_key": "features",
        },
        {
            "agent_id": "memory",
            "input_key": "user_id",
            "output_key": "user_context",
        },
        {
            "agent_id": "recommender",
            "input_key": "features",
            "output_key": "recommendation",
        },
        {
            "agent_id": "memory",
            "input_key": "recommendation",
            "output_key": "update_result",
        },
    ]


def get_chat_workflow() -> List[Dict[str, Any]]:
    """Get the AI chat workflow with agent collaboration.

    This workflow demonstrates dynamic agent collaboration:
    1. MemoryAgent → Load user profile
    2. ReActAgent → Process query with tool calling
    3. MemoryAgent → Update conversation context
    """
    return [
        {
            "agent_id": "memory",
            "input_key": "user_id",
            "output_key": "user_context",
        },
        {
            "agent_id": "react",
            "input_key": "question",
            "output_key": "chat_response",
        },
        {
            "agent_id": "memory",
            "input_key": "chat_response",
            "output_key": "context_update",
        },
    ]

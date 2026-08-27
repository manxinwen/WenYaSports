"""Plan Parser: LLM 生成计划的结构化解析与验证。

将 LLM 输出的 JSON 计划转换为强类型的 ExecutionPlan 对象，
并提供验证、依赖检查等工具方法。
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class PlanStep:
    """计划中的单个执行步骤。

    Attributes:
        step: 步骤序号 (1-based)
        agent_id: 目标 Agent ID
        capability: 需要的能力描述（LLM 通过此匹配 Agent）
        input_key: 从上一步结果中取输入的 key
        output_key: 本步输出存入 results 的 key
        params: 传给 Agent 的额外参数
        reasoning: LLM 选择此步骤的推理
        condition: 前置条件（可选），如 "step_1_output.success == true"
    """

    step: int
    agent_id: str
    capability: str = ""
    input_key: Optional[str] = None
    output_key: Optional[str] = None
    params: Dict[str, Any] = field(default_factory=dict)
    reasoning: str = ""
    condition: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PlanStep":
        return cls(
            step=data.get("step", 0),
            agent_id=data.get("agent_id", ""),
            capability=data.get("capability", ""),
            input_key=data.get("input_key"),
            output_key=data.get("output_key"),
            params=data.get("params", {}),
            reasoning=data.get("reasoning", ""),
            condition=data.get("condition"),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step": self.step,
            "agent_id": self.agent_id,
            "capability": self.capability,
            "input_key": self.input_key,
            "output_key": self.output_key,
            "params": self.params,
            "reasoning": self.reasoning,
            "condition": self.condition,
        }


@dataclass
class ExecutionPlan:
    """完整的执行计划。

    Attributes:
        goal: 要达成的目标
        steps: 有序的步骤列表
        fallback_steps: 主计划失败后的降级步骤
        confidence: LLM 对计划的置信度 (0-1)
        reasoning: LLM 生成此计划的整体推理
    """

    goal: str
    steps: List[PlanStep] = field(default_factory=list)
    fallback_steps: List[PlanStep] = field(default_factory=list)
    confidence: float = 1.0
    reasoning: str = ""

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExecutionPlan":
        steps = [PlanStep.from_dict(s) for s in data.get("plan", [])]
        fallback_steps = [
            PlanStep.from_dict(s) for s in data.get("fallback_plan", [])
        ]
        return cls(
            goal=data.get("goal", ""),
            steps=steps,
            fallback_steps=fallback_steps,
            confidence=data.get("confidence", 1.0),
            reasoning=data.get("reasoning", ""),
        )

    @classmethod
    def from_json(cls, json_str: str) -> "ExecutionPlan":
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError:
            logger.error("Failed to parse LLM plan JSON")
            return cls(goal="", steps=[])
        return cls.from_dict(data)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "goal": self.goal,
            "plan": [s.to_dict() for s in self.steps],
            "fallback_plan": [s.to_dict() for s in self.fallback_steps],
            "confidence": self.confidence,
            "reasoning": self.reasoning,
        }

    def validate(self, available_agent_ids: List[str]) -> List[str]:
        """验证计划中的 Agent 是否都可用。

        Returns:
            错误信息列表（空列表表示验证通过）
        """
        errors = []
        all_steps = self.steps + self.fallback_steps
        for step in all_steps:
            if step.agent_id and step.agent_id not in available_agent_ids:
                errors.append(
                    f"Step {step.step}: Agent '{step.agent_id}' not available. "
                    f"Available: {available_agent_ids}"
                )
        return errors

    def get_execution_order(self) -> List[PlanStep]:
        """返回按 step 排序的步骤列表。"""
        return sorted(self.steps, key=lambda s: s.step)

    def is_empty(self) -> bool:
        return len(self.steps) == 0


def build_fallback_plan(goal: str) -> ExecutionPlan:
    """构建规则驱动的降级计划（LLM 不可用时使用）。"""
    return ExecutionPlan(
        goal=goal,
        steps=[
            PlanStep(
                step=1,
                agent_id="parser",
                capability="fit_parsing",
                input_key="file_path",
                output_key="parsed_activity",
                reasoning="规则降级：优先解析文件",
            ),
            PlanStep(
                step=2,
                agent_id="feature_extractor",
                capability="feature_engineering",
                input_key="parsed_activity",
                output_key="features",
                reasoning="规则降级：提取特征",
            ),
            PlanStep(
                step=3,
                agent_id="memory",
                capability="context_retrieval",
                input_key="user_context",
                output_key="memory_context",
                reasoning="规则降级：获取记忆上下文",
            ),
            PlanStep(
                step=4,
                agent_id="recommender",
                capability="training_advice",
                input_key="features",
                output_key="recommendation",
                reasoning="规则降级：生成建议",
            ),
        ],
        confidence=0.5,
        reasoning="LLM 不可用，使用预定义流水线",
    )
"""LLM Orchestrator: 由大模型驱动的智能多Agent编排引擎。

核心能力：
1. 意图分析：LLM 理解用户目标，拆解为可执行的子任务
2. 能力匹配：根据 Agent 注册表的能力声明，智能选择最合适的 Agent
3. 计划生成：生成包含主计划 + 降级计划的完整执行方案
4. 动态重规划：执行失败时，LLM 自动调整策略
5. 可观测性：每一步推理都被 Trace Collector 记录
6. 质量闭环：Evaluator 评估产出 → Reflection 反思失败 → Guardrails 守卫输出
7. Agent 协商：多 Agent 能力争议通过协商协议解决
8. 决策可解释：每个决策都生成人类可读的解释

设计理念：
- Agent 是「能力提供者」，声明自己能做什么
- Orchestrator 是「智能项目经理」，根据需求选择和编排 Agent
- LLM 负责「思考」，Harness 负责「执行」，Governance 负责「守门」
- Evaluator 负责「质检」，Reflection 负责「学习」，Guardrails 负责「安全」
- Negotiation 负责「协作」，Explainability 负责「透明」
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Callable, Dict, List, Optional

from app.agents.evaluator_agent import EvaluatorAgent
from app.agents.guardrails import Guardrails
from app.agents.reflection_engine import ReflectionEngine
from app.harness.harness import Harness
from app.harness.agent_registry import AgentStatus
from app.orchestrator.negotiation import (
    AgentProposal,
    NegotiationResult,
    NegotiationSession,
    NegotiationType,
    ProposalRank,
)
from app.orchestrator.explainability import (
    DecisionRecord,
    ExplainabilityEngine,
    ExplainabilityType,
)
from app.orchestrator.plan_parser import (
    ExecutionPlan,
    PlanStep,
    build_fallback_plan,
)
from app.trace import trace_collector

logger = logging.getLogger(__name__)

PLANNER_SYSTEM_PROMPT = """你是一个多智能体系统的编排引擎。你的任务是根据用户目标和可用的 Agent 能力，生成最优的执行计划。

## 可用 Agent 及其能力
{agent_capabilities}

## 规划原则
1. **能力匹配**：选择最匹配子任务的 Agent，而非硬编码顺序
2. **依赖感知**：确保后续步骤的输入依赖于前序步骤的输出
3. **容错设计**：为主计划中的每个关键步骤设计降级方案
4. **数据驱动**：明确每个步骤的 input_key（从前序结果取数据）和 output_key（输出到 results 的 key）
5. **最小化步骤**：用最少的步骤完成目标，避免不必要的 Agent 调用

## 输出格式
严格输出 JSON，不要输出其他内容：
```json
{{
  "goal": "用户的原始目标",
  "plan": [
    {{
      "step": 1,
      "agent_id": "agent_id",
      "capability": "需要的能力",
      "input_key": "从前序结果取值的key（第一步可为空或初始输入key）",
      "output_key": "本步输出存入results的key",
      "params": {{}},
      "reasoning": "选择此Agent的推理"
    }}
  ],
  "fallback_plan": [同上格式的降级步骤],
  "confidence": 0.0-1.0,
  "reasoning": "整体规划思路"
}}
```

## 注意
- input_key 指向前序步骤 output_key 的值，或特殊值：file_path（初始文件）、user_context（用户上下文）
- 如果目标不需要特定 Agent，直接返回空计划 confidence=0
- 优先使用能力最匹配的 Agent，而非默认顺序"""

PLANNER_REPLAN_PROMPT = """上一轮执行中出现了问题。请根据执行历史重新规划。

## 原始目标
{goal}

## 执行历史
{execution_history}

## 可用 Agent
{agent_capabilities}

## 重新规划原则
1. **分析失败原因**：判断是 Agent 能力不足还是数据问题
2. **选择替代方案**：优先选择能力重叠的其他 Agent
3. **简化计划**：如果可能，跳过失败步骤或合并操作
4. **保留成功步骤**：已成功的步骤不需要重新执行

严格输出 JSON 格式的新计划。"""


class LLMOrchestrator:
    """LLM 驱动的智能编排引擎。

    Usage:
        orchestrator = LLMOrchestrator(harness, llm_client=my_llm)
        result = orchestrator.execute_goal(
            goal="分析这份运动数据并给出建议",
            initial_input={"file_path": "/path/to/activity.fit"},
            user_id="user_001",
        )
    """

    def __init__(
        self,
        harness: Harness,
        llm_client: Optional[Any] = None,
        model: str = "gpt-4o-mini",
        max_replanning: int = 3,
        trace_collector_instance=None,
        evaluator: Optional[EvaluatorAgent] = None,
        reflection_engine: Optional[ReflectionEngine] = None,
        guardrails: Optional[Guardrails] = None,
        quality_threshold: float = 6.0,
        enable_quality_loop: bool = True,
        enable_negotiation: bool = True,
        enable_explainability: bool = True,
    ):
        self.harness = harness
        self.llm_client = llm_client
        self.model = model
        self.max_replanning = max_replanning
        self._trace = trace_collector_instance or trace_collector
        self._planning_count = 0
        self._replan_count = 0

        # 质量闭环组件（可选注入）
        self.evaluator = evaluator or EvaluatorAgent(llm_enabled=False)
        self.reflection_engine = reflection_engine
        self.guardrails = guardrails or Guardrails()
        self.quality_threshold = quality_threshold
        self.enable_quality_loop = enable_quality_loop
        self._quality_check_count = 0
        self._quality_fail_count = 0

        # Agent 协商协议
        self.enable_negotiation = enable_negotiation
        self._negotiation_count = 0
        self._negotiation_success = 0

        # 决策可解释层
        self.enable_explainability = enable_explainability
        self.explainability_engine = ExplainabilityEngine()
        self._decision_count = 0

    # ------------------------------------------------------------------
    # 核心入口
    # ------------------------------------------------------------------
    def execute_goal(
        self,
        goal: str,
        initial_input: Any,
        user_id: str = "default",
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """执行完整的 LLM 编排流程。

        Args:
            goal: 用户目标描述
            initial_input: 初始输入数据
            user_id: 用户标识
            session_id: 会话标识

        Returns:
            包含执行结果、计划、追踪的完整返回
        """
        import uuid

        session = session_id or str(uuid.uuid4())
        self._trace.record_session_start(
            session_id=session,
            user_request=goal,
            user_id=user_id,
        )

        self._trace.add_step(
            session_id=session,
            agent_name="llm_orchestrator",
            step_type="thought",
            detail={"goal": goal},
            thought=f"开始编排目标: {goal}",
        )

        # Phase 1: 生成执行计划
        plan = self._generate_plan(goal, initial_input, session)

        # 记录计划生成决策（可解释性）
        if self.enable_explainability:
            self.explainability_engine.record_decision(
                decision_type=ExplainabilityType.PLAN_GENERATION,
                context={"goal": goal, "session_id": session},
                chosen_option=plan.plan_id if hasattr(plan, "plan_id") else "dynamic_plan",
                reasoning=f"LLM 生成 {len(plan.steps)} 步执行计划",
                metadata={"steps_count": len(plan.steps)},
            )
            self._decision_count += 1

        if plan.is_empty():
            self._trace.add_step(
                session_id=session,
                agent_name="llm_orchestrator",
                step_type="final",
                detail={"reason": "无法生成有效计划"},
                thought="LLM 无法生成有效计划，目标可能超出系统能力",
            )
            self._trace.record_session_end(
                session_id=session, success=False, total_steps=0
            )
            return {
                "success": False,
                "error": "无法生成有效执行计划",
                "session_id": session,
            }

        # Phase 2: 执行计划（含重规划）
        result = self._execute_plan_with_replan(
            plan, goal, initial_input, session, user_id
        )

        # Phase 3: 质量闭环（可选）
        if self.enable_quality_loop and result.get("success"):
            result = self._run_quality_loop(result, goal, session, user_id)

        self._trace.record_session_end(
            session_id=session,
            success=result.get("success", False),
            total_steps=len(plan.steps),
        )

        return result

    # ------------------------------------------------------------------
    # Phase 1: 计划生成
    # ------------------------------------------------------------------
    def _generate_plan(
        self,
        goal: str,
        initial_input: Any,
        session_id: str,
    ) -> ExecutionPlan:
        """调用 LLM 生成执行计划。"""
        self._planning_count += 1

        agent_caps = self._format_agent_capabilities()
        prompt = PLANNER_SYSTEM_PROMPT.format(agent_capabilities=agent_caps)

        self._trace.add_step(
            session_id=session_id,
            agent_name="llm_orchestrator",
            step_type="action",
            detail={
                "model": self.model,
                "available_agents_count": len(self.harness.registry.list_agents()),
            },
            thought=f"请求 LLM 生成执行计划（{len(self.harness.registry.list_agents())} 个可用 Agent）",
        )

        plan_data = None
        llm_available = self.llm_client is not None

        if llm_available:
            try:
                plan_data = self._call_llm_for_plan(
                    prompt, goal, initial_input
                )
            except Exception as exc:
                logger.warning("LLM 计划生成失败，降级: %s", exc)
                self._trace.add_step(
                    session_id=session_id,
                    agent_name="llm_orchestrator",
                    step_type="observation",
                    detail={"error": str(exc)},
                    thought=f"LLM 调用失败: {exc}，使用降级计划",
                )
                llm_available = False

        if not llm_available or plan_data is None:
            plan = build_fallback_plan(goal)
            self._trace.add_step(
                session_id=session_id,
                agent_name="llm_orchestrator",
                step_type="observation",
                detail={"plan_type": "fallback", "steps": len(plan.steps)},
                thought="使用规则降级计划（LLM 不可用）",
            )
            return plan

        plan = ExecutionPlan.from_dict(plan_data)

        # Validate plan
        available_ids = [
            a["agent_id"] for a in self.harness.registry.list_agents()
        ]
        errors = plan.validate(available_ids)
        if errors:
            logger.warning("Plan validation failed: %s", errors)
            self._trace.add_step(
                session_id=session_id,
                agent_name="llm_orchestrator",
                step_type="observation",
                detail={"errors": errors},
                thought=f"计划验证失败: {errors}，使用降级计划",
            )
            return build_fallback_plan(goal)

        self._trace.add_step(
            session_id=session_id,
            agent_name="llm_orchestrator",
            step_type="observation",
            detail={
                "plan_steps": len(plan.steps),
                "confidence": plan.confidence,
                "reasoning": plan.reasoning[:200],
            },
            thought=f"LLM 生成计划成功: {len(plan.steps)} 步，置信度 {plan.confidence:.2f}",
        )

        return plan

    def _call_llm_for_plan(
        self,
        system_prompt: str,
        goal: str,
        initial_input: Any,
    ) -> Optional[Dict[str, Any]]:
        """调用 LLM 获取计划 JSON。"""
        from openai import OpenAI

        api_key = os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            return None

        client = self.llm_client or OpenAI(api_key=api_key)

        user_msg = f"目标: {goal}\n初始输入: {json.dumps(initial_input, ensure_ascii=False, default=str)[:500]}"

        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.1,
            max_tokens=2000,
        )

        raw = response.choices[0].message.content.strip()
        # Extract JSON from response (handle markdown code blocks)
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1] if "\n" in raw else raw[3:]
            raw = raw.rsplit("```", 1)[0]

        return json.loads(raw)

    # ------------------------------------------------------------------
    # Phase 2: 计划执行 + 重规划
    # ------------------------------------------------------------------
    def _execute_plan_with_replan(
        self,
        plan: ExecutionPlan,
        goal: str,
        initial_input: Any,
        session_id: str,
        user_id: str,
    ) -> Dict[str, Any]:
        """执行计划，失败时触发重规划。"""
        results: Dict[str, Any] = {"_initial_input": initial_input}
        history: List[Dict[str, Any]] = []
        current_plan = plan
        replan_count = 0

        while replan_count <= self.max_replanning:
            execution_result = self._execute_single_plan(
                current_plan, results, session_id
            )

            if execution_result.get("success"):
                return {
                    "success": True,
                    "session_id": session_id,
                    "plan_used": current_plan.to_dict(),
                    "results": execution_result.get("results", results),
                    "steps_completed": execution_result.get("completed", 0),
                    "replans": replan_count,
                }

            # Plan failed — try to replan
            history.append(execution_result)
            failed_step = execution_result.get("failed_step", "unknown")
            error = execution_result.get("error", "Unknown error")

            self._replan_count += 1
            replan_count += 1

            self._trace.add_step(
                session_id=session_id,
                agent_name="llm_orchestrator",
                step_type="thought",
                detail={
                    "failed_step": failed_step,
                    "error": error,
                    "replan_count": replan_count,
                },
                thought=f"步骤 {failed_step} 失败: {error}。触发第 {replan_count} 次重规划",
            )

            # Try LLM replanning
            new_plan = self._replan(
                goal, history, current_plan, session_id
            )

            if new_plan is None or new_plan.is_empty():
                # Try fallback plan from current plan
                if current_plan.fallback_steps:
                    new_plan = ExecutionPlan(
                        goal=goal,
                        steps=current_plan.fallback_steps,
                        confidence=0.3,
                        reasoning="使用预设降级计划",
                    )
                else:
                    # Last resort: build a fresh fallback
                    new_plan = build_fallback_plan(goal)
                    # Skip already-succeeded steps
                    new_plan.steps = self._skip_completed_steps(
                        new_plan.steps, results
                    )

            if not new_plan.is_empty():
                current_plan = new_plan
                # Reset results for failed steps (keep succeeded ones)
                self._trace.add_step(
                    session_id=session_id,
                    agent_name="llm_orchestrator",
                    step_type="action",
                    detail={
                        "new_plan_steps": len(new_plan.steps),
                        "reasoning": new_plan.reasoning[:200],
                    },
                    thought=f"新计划: {len(new_plan.steps)} 步，重新开始执行",
                )
                continue

            # Truly stuck
            return {
                "success": False,
                "session_id": session_id,
                "error": f"执行失败且无法重规划（已尝试 {replan_count} 次）",
                "failed_step": failed_step,
                "results": results,
                "replans": replan_count,
            }

        # Exhausted replanning
        return {
            "success": False,
            "session_id": session_id,
            "error": f"重规划次数已达上限 ({self.max_replanning})",
            "results": results,
            "replans": replan_count,
        }

    def _execute_single_plan(
        self,
        plan: ExecutionPlan,
        results: Dict[str, Any],
        session_id: str,
    ) -> Dict[str, Any]:
        """执行单个计划的所有步骤。"""
        completed = 0
        results_local = dict(results)

        for i, step in enumerate(plan.get_execution_order()):
            # Resolve input for this step
            step_args = self._resolve_agent_inputs(step, results_local)

            # Agent 协商：如果有多个 Agent 声称具备相同能力，通过协商选出最优
            resolved_agent_id = step.agent_id
            if self.enable_negotiation:
                negotiated = self._try_negotiate_agent(
                    step.agent_id, step.reasoning or str(step_args), session_id
                )
                if negotiated and negotiated != step.agent_id:
                    self._trace.add_step(
                        session_id=session_id,
                        agent_name="llm_orchestrator",
                        step_type="thought",
                        detail={
                            "original_agent": step.agent_id,
                            "negotiated_agent": negotiated,
                        },
                        thought=f"Agent 协商: {step.agent_id} → {negotiated}",
                    )
                    resolved_agent_id = negotiated

            # 记录 Agent 选择决策（可解释性）
            if self.enable_explainability and resolved_agent_id != step.agent_id:
                self.explainability_engine.record_decision(
                    decision_type=ExplainabilityType.AGENT_SELECTION,
                    context={
                        "step": step.step,
                        "task": step.reasoning or f"step_{i}",
                        "original_agent": step.agent_id,
                    },
                    chosen_option=resolved_agent_id,
                    reasoning="通过协商协议选出更优 Agent",
                    alternatives=[step.agent_id],
                )
                self._decision_count += 1

            self._trace.add_step(
                session_id=session_id,
                agent_name="llm_orchestrator",
                step_type="action",
                detail={
                    "step": step.step,
                    "agent_id": resolved_agent_id,
                    "output_key": step.output_key,
                    "reasoning": step.reasoning[:100],
                },
                thought=f"步骤 {step.step}: 委托 {resolved_agent_id} 执行 (args={list(step_args.keys())})",
            )

            # Execute via harness
            exec_result = self._execute_agent_with_args(
                resolved_agent_id, step_args
            )

            if not exec_result.get("success"):
                self._trace.add_step(
                    session_id=session_id,
                    agent_name="llm_orchestrator",
                    step_type="observation",
                    detail={
                        "step": step.step,
                        "error": exec_result.get("error", "Unknown"),
                    },
                    thought=f"步骤 {step.step} ({step.agent_id}) 失败",
                )
                return {
                    "success": False,
                    "failed_step": step.step,
                    "failed_agent": step.agent_id,
                    "error": exec_result.get("error", "Unknown error"),
                    "completed": completed,
                    "results": results_local,
                }

            # Store result
            output_key = step.output_key or f"step_{i}_output"
            results_local[output_key] = exec_result.get("result")
            completed += 1

            self._trace.add_step(
                session_id=session_id,
                agent_name="llm_orchestrator",
                step_type="observation",
                detail={
                    "step": step.step,
                    "agent_id": step.agent_id,
                    "output_key": output_key,
                    "success": True,
                },
                thought=f"步骤 {step.step} ({step.agent_id}) 完成，输出存入 {output_key}",
            )

        return {
            "success": True,
            "completed": completed,
            "results": results_local,
        }

    def _execute_agent_with_args(
        self, agent_id: str, kwargs: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute an agent with keyword arguments via the harness.

        Uses reflection to adapt to each agent's run() signature.
        Falls back gracefully if signature doesn't match.
        """
        import inspect

        agent_instance = self.harness.registry.get_instance(agent_id)
        if agent_instance is None:
            return {"success": False, "error": f"Agent '{agent_id}' not found"}

        # Execute through harness governance
        try:
            def execute_fn():
                sig = inspect.signature(agent_instance.run)
                params = sig.parameters

                # If agent accepts **kwargs, pass everything
                accepts_kwargs = any(
                    p.kind == inspect.Parameter.VAR_KEYWORD
                    for p in params.values()
                )

                if accepts_kwargs:
                    return agent_instance.run(**kwargs)

                # Otherwise, filter to matching parameter names
                bound_kwargs = {}
                for name, param in params.items():
                    if name == "self":
                        continue
                    if name in kwargs:
                        bound_kwargs[name] = kwargs[name]
                    elif param.default is not inspect.Parameter.empty:
                        bound_kwargs[name] = param.default

                return agent_instance.run(**bound_kwargs)

            result = self.harness.governance.execute_with_governance(
                agent_id=agent_id,
                execution_fn=execute_fn,
                context={
                    "agent_id": agent_id,
                    "tokens_used": 0,
                    "execution_time_ms": 0,
                },
            )

            # Update agent status
            if result.get("success"):
                self.harness.registry.set_status(agent_id, AgentStatus.IDLE)
                self.harness.registry.increment_execution(agent_id)
            else:
                self.harness.registry.set_status(agent_id, AgentStatus.ERROR)

            return result

        except Exception as exc:
            logger.exception("Agent execution failed: %s", exc)
            self.harness.registry.set_status(agent_id, "error")
            return {"success": False, "error": str(exc)}

    # ------------------------------------------------------------------
    # Agent Negotiation: 多 Agent 协商选择
    # ------------------------------------------------------------------

    def _try_negotiate_agent(
        self,
        primary_agent_id: str,
        task_description: str,
        session_id: str,
    ) -> Optional[str]:
        """尝试通过协商协议选择更优的 Agent。

        场景：当有多个 Agent 声称具备同一能力时（如 feature_extractor
        和 react 都能做特征提取），通过协商选出最合适的。

        Args:
            primary_agent_id: 主选 Agent
            task_description: 任务描述
            session_id: 会话 ID

        Returns:
            协商后选定的 Agent ID；如果无更优选择则返回 None
        """
        # 查找具备相同或相关能力的候选 Agent
        candidates = self._find_capability_candidates(primary_agent_id)

        if len(candidates) <= 1:
            return None  # 没有其他候选，直接用主选

        # 构建协商会话
        session = NegotiationSession(
            negotiation_type=NegotiationType.CAPABILITY_DISPUTE,
            topic=f"能力协商: {task_description[:50]}",
            max_rounds=2,
        )
        session.start_round()

        # 为每个候选构建提案
        for candidate_id in candidates:
            descriptor = self.harness.registry.get_descriptor(candidate_id)
            quality_score = 0.5
            confidence = 0.5
            reasoning = ""

            if descriptor:
                # 基于 Agent 描述符构建评分
                capabilities = getattr(descriptor, 'capabilities', [])
                execution_count = getattr(descriptor, 'execution_count', 0)
                error_count = getattr(descriptor, 'error_count', 0)

                # 计算置信度和质量分
                if capabilities:
                    confidence = min(1.0, len(capabilities) * 0.2 + 0.3)
                if execution_count > 0:
                    success_rate = max(0.0, 1.0 - error_count / max(execution_count, 1))
                    quality_score = success_rate * 0.8 + 0.2

                reasoning = f"能力: {', '.join(capabilities[:3])}" if capabilities else "通用 Agent"

            proposal = AgentProposal(
                agent_id=candidate_id,
                capability=task_description[:30],
                confidence=confidence,
                quality_score=quality_score,
                reasoning=reasoning,
                arguments=[f"历史执行: {executions}次"] if executions > 0 else ["新 Agent"],
            )
            session.add_proposal(proposal)

        # 执行协商
        result = session.resolve(strategy="hybrid")
        self._negotiation_count += 1

        if result.success and result.winner_id != primary_agent_id:
            self._negotiation_success += 1

            # 记录协商决策
            if self.enable_explainability:
                self.explainability_engine.record_decision(
                    decision_type=ExplainabilityType.NEGOTIATION,
                    context={
                        "topic": f"能力协商: {task_description[:50]}",
                        "consensus_type": result.consensus_type,
                        "session_id": session_id,
                    },
                    chosen_option=result.winner_id or primary_agent_id,
                    reasoning=result.explanation,
                    alternatives=[c for c in candidates if c != result.winner_id],
                    scores=result.all_scores,
                )
                self._decision_count += 1

            logger.info(
                "Agent 协商结果: %s → %s (理由: %s)",
                primary_agent_id, result.winner_id, result.explanation[:100],
            )
            return result.winner_id

        return None

    def _find_capability_candidates(
        self, primary_agent_id: str
    ) -> List[str]:
        """查找具备相似能力的候选 Agent。

        Args:
            primary_agent_id: 主选 Agent ID

        Returns:
            候选 Agent ID 列表（包含主选）
        """
        candidates = [primary_agent_id]

        # 获取主选 Agent 的能力
        primary_descriptor = self.harness.registry.get_descriptor(primary_agent_id)
        primary_capabilities = set()
        if primary_descriptor:
            primary_capabilities = set(
                getattr(primary_descriptor, 'capabilities', [])
            )

        # 查找其他具备相同能力的 Agent
        agent_list = self.harness.registry.list_agents()
        for agent_entry in agent_list:
            # list_agents 返回 Dict 列表，取 agent_id 字段
            agent_id = (
                agent_entry.get('agent_id')
                if isinstance(agent_entry, dict)
                else agent_entry
            )
            if not agent_id or agent_id == primary_agent_id:
                continue

            descriptor = self.harness.registry.get_descriptor(agent_id)
            if not descriptor:
                continue

            agent_caps = set(getattr(descriptor, 'capabilities', []))
            # 如果有能力重叠或 Agent 名称暗示相关能力
            if agent_caps & primary_capabilities:
                candidates.append(agent_id)
            elif self._is_functionally_equivalent(agent_id, primary_agent_id):
                candidates.append(agent_id)

        return candidates

    @staticmethod
    def _is_functionally_equivalent(agent_id: str, target_id: str) -> bool:
        """判断两个 Agent 是否功能等价（基于名称启发式）。

        Args:
            agent_id: 候选 Agent ID
            target_id: 目标 Agent ID

        Returns:
            是否功能等价
        """
        # 功能等价的 Agent 对（frozenset 实现无序配对）
        equivalent_pairs = [
            frozenset({"feature_extractor_agent", "reaact_agent"}),
            frozenset({"parser_agent", "reaact_agent"}),
            frozenset({"memory_agent", "coordinator_agent"}),
            frozenset({"recommendation_agent", "reaact_agent"}),
            frozenset({"reaact_agent", "coordinator_agent"}),
        ]

        pair = frozenset({agent_id, target_id})
        return pair in equivalent_pairs

    def get_orchestrator_stats(self) -> Dict[str, Any]:
        """获取 Orchestrator 统计信息。"""
        stats = {
            "planning_count": self._planning_count,
            "replan_count": self._replan_count,
            "negotiation_count": self._negotiation_count,
            "negotiation_success": self._negotiation_success,
            "decision_count": self._decision_count,
            "quality_check_count": self._quality_check_count,
            "quality_fail_count": self._quality_fail_count,
            "enable_negotiation": self.enable_negotiation,
            "enable_explainability": self.enable_explainability,
        }

        if self.enable_explainability:
            explain_stats = self.explainability_engine.get_stats()
            stats["explainability"] = explain_stats

        return stats

    def _run_quality_loop(
        self,
        result: Dict[str, Any],
        goal: str,
        session_id: str,
        user_id: str,
    ) -> Dict[str, Any]:
        """执行质量闭环：评估 → 反思 → 守卫。

        流程：
        1. 从执行结果中提取最终产出文本
        2. EvaluatorAgent 进行多维度质量评估
        3. 若低于阈值，ReflectionEngine 分析失败原因
        4. Guardrails 进行输出安全守卫
        5. 返回增强后的结果

        Args:
            result: 执行结果
            goal: 原始目标
            session_id: 会话标识
            user_id: 用户标识

        Returns:
            增强后的结果（含质量评估信息）
        """
        self._trace.add_step(
            session_id=session_id,
            agent_name="llm_orchestrator",
            step_type="thought",
            detail={"phase": "quality_loop"},
            thought="启动质量闭环：Evaluator → Reflection → Guardrails",
        )

        # 提取最终产出
        output_text = self._extract_output_text(result)
        if not output_text:
            return result

        # 1. Evaluator 评估
        self._quality_check_count += 1
        eval_result = self.evaluator.evaluate(
            output=output_text,
            goal=goal,
            context={"user_id": user_id},
        )

        self._trace.add_step(
            session_id=session_id,
            agent_name="llm_orchestrator",
            step_type="observation",
            detail={
                "quality_score": eval_result.overall_score,
                "passed": eval_result.passed,
                "threshold": self.quality_threshold,
            },
            thought=f"质量评估: {eval_result.overall_score}/10 "
                    f"{'通过' if eval_result.passed else '未通过'}",
        )

        result["quality_evaluation"] = eval_result.to_dict()

        # 2. 若质量不达标，触发反思
        if not eval_result.passed and self.reflection_engine:
            self._quality_fail_count += 1
            try:
                reflection = self.reflection_engine.reflect_on_failure(
                    task_type="analysis",
                    original_goal=goal,
                    execution_result=result,
                    evaluation_feedback={
                        "score": eval_result.overall_score,
                        "issues": [d.comment for d in eval_result.dimensions
                                   if d.score < self.quality_threshold],
                        "suggestions": eval_result.suggestions,
                    },
                )
                result["reflection"] = reflection.to_dict()

                self._trace.add_step(
                    session_id=session_id,
                    agent_name="llm_orchestrator",
                    step_type="thought",
                    detail={
                        "root_cause": reflection.root_cause[:100],
                        "confidence": reflection.confidence,
                    },
                    thought=f"质量反思: 根因={reflection.root_cause[:50]}... "
                            f"信心={reflection.confidence:.2f}",
                )
            except Exception as exc:
                logger.warning("Reflection failed: %s", exc)

        # 3. Guardrails 安全守卫
        try:
            guard_result = self.guardrails.guard(
                output=output_text,
                context={"user_id": user_id, "goal": goal},
            )
            result["guardrails"] = guard_result.to_dict()

            if not guard_result.passed and guard_result.sanitized_output:
                result["sanitized_output"] = guard_result.sanitized_output
                self._trace.add_step(
                    session_id=session_id,
                    agent_name="llm_orchestrator",
                    step_type="observation",
                    detail={
                        "sanitized": True,
                        "issues": guard_result.issues,
                    },
                    thought=f"安全守卫: 检测到 {len(guard_result.issues)} 个问题，"
                            f"输出已脱敏处理",
                )
        except Exception as exc:
            logger.warning("Guardrails check failed: %s", exc)

        # 添加质量统计
        result["quality_stats"] = {
            "total_checks": self._quality_check_count,
            "failures": self._quality_fail_count,
            "threshold": self.quality_threshold,
        }

        return result

    def _extract_output_text(self, result: Dict[str, Any]) -> str:
        """从执行结果中提取可评估的产出文本。"""
        results_data = result.get("results", {})
        if not results_data:
            return ""

        # 查找最终产出（通常是最后一个 output_key）
        output_keys = [k for k in results_data.keys()
                       if k not in ("_initial_input", "user_context")]
        if not output_keys:
            return ""

        # 取最后一个非字典类型的结果作为产出
        for key in reversed(output_keys):
            value = results_data[key]
            if isinstance(value, str) and len(value) > 10:
                return value
            elif isinstance(value, dict):
                # 尝试从 dict 中提取 answer/response 字段
                for field in ("answer", "response", "output", "result", "summary"):
                    if field in value and isinstance(value[field], str):
                        return value[field]

        return ""

    # ------------------------------------------------------------------
    # Re-planning
    # ------------------------------------------------------------------
    def _replan(
        self,
        goal: str,
        history: List[Dict[str, Any]],
        current_plan: ExecutionPlan,
        session_id: str,
    ) -> Optional[ExecutionPlan]:
        """调用 LLM 进行重规划。"""
        if self.llm_client is None:
            return None

        agent_caps = self._format_agent_capabilities()

        exec_history_text = json.dumps(
            [
                {
                    "step": h.get("failed_step"),
                    "agent": h.get("failed_agent"),
                    "error": h.get("error"),
                    "completed": h.get("completed"),
                }
                for h in history
            ],
            ensure_ascii=False,
            default=str,
        )

        prompt = PLANNER_REPLAN_PROMPT.format(
            goal=goal,
            execution_history=exec_history_text,
            agent_capabilities=agent_caps,
        )

        self._trace.add_step(
            session_id=session_id,
            agent_name="llm_orchestrator",
            step_type="action",
            detail={"history_length": len(history)},
            thought="请求 LLM 重新规划执行路径",
        )

        try:
            plan_data = self._call_llm_for_plan(prompt, goal, {})
            if plan_data:
                plan = ExecutionPlan.from_dict(plan_data)
                available_ids = [
                    a["agent_id"]
                    for a in self.harness.registry.list_agents()
                ]
                errors = plan.validate(available_ids)
                if not errors and not plan.is_empty():
                    return plan
        except Exception as exc:
            logger.warning("Re-planning failed: %s", exc)

        return None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _resolve_agent_inputs(
        self, step: PlanStep, results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """解析步骤的输入参数，生成匹配 Agent 签名的 kwargs。

        根据 step.input_key 从 results 中取数据，
        再结合 step.params 生成完整的关键字参数字典。
        """
        kwargs: Dict[str, Any] = {}

        # 1. Resolve the main input data
        main_input = self._resolve_input(step, results)

        # 2. Apply step-specific params (from plan or default)
        agent_id = step.agent_id
        params = step.params or {}

        # Build kwargs based on agent_id conventions
        if agent_id == "parser":
            # ParserAgent.run(file_path: str)
            if isinstance(main_input, dict) and "file_path" in main_input:
                kwargs["file_path"] = main_input["file_path"]
            elif isinstance(main_input, str):
                kwargs["file_path"] = main_input
            else:
                kwargs["file_path"] = main_input

        elif agent_id == "feature_extractor":
            # FeatureExtractorAgent.run(activity: ParsedActivity)
            kwargs["activity"] = main_input

        elif agent_id == "memory":
            # MemoryAgent.run(user_id, session_id)
            initial = results.get("_initial_input", {})
            if isinstance(initial, dict):
                kwargs["user_id"] = initial.get("user_id", "default")
                kwargs["session_id"] = initial.get("session_id", "default")
            kwargs.update(params)

        elif agent_id == "recommender":
            # RecommendationAgent.run(features, user_profile, short_term_context)
            kwargs["features"] = main_input
            kwargs["user_profile"] = results.get("user_context", {}).get(
                "user_profile", {}
            )
            kwargs["short_term_context"] = results.get("user_context", {}).get(
                "short_term_context", {}
            )
            kwargs.update(params)

        elif agent_id == "react":
            # ReActAgent.run(question, user_id, session_id)
            if isinstance(main_input, dict):
                kwargs["question"] = main_input.get("question", str(main_input))
                kwargs["user_id"] = main_input.get("user_id", "default")
            else:
                kwargs["question"] = str(main_input)
            kwargs.update(params)

        else:
            # Generic fallback: pass everything
            if isinstance(main_input, dict):
                kwargs = dict(main_input)
            else:
                kwargs["input_data"] = main_input
            kwargs.update(params)

        return kwargs

    def _resolve_input(
        self, step: PlanStep, results: Dict[str, Any]
    ) -> Any:
        """从 results 中解析步骤的主输入数据。"""
        if step.input_key is None:
            return results.get("_initial_input")

        if step.input_key == "file_path":
            initial = results.get("_initial_input")
            if isinstance(initial, dict):
                return initial.get("file_path", initial)
            return initial

        if step.input_key == "user_context":
            initial = results.get("_initial_input", {})
            return {
                "user_id": initial.get("user_id", "default"),
                "session_id": initial.get("session_id", "default"),
            }

        value = results.get(step.input_key)
        if value is not None:
            return value

        initial = results.get("_initial_input")
        if isinstance(initial, dict) and step.input_key in initial:
            return initial[step.input_key]

        return initial

    def _format_agent_capabilities(self) -> str:
        """格式化所有 Agent 的能力声明供 LLM 使用。"""
        agents = self.harness.registry.list_agents()
        lines = []
        for a in agents:
            caps = ", ".join(a.get("capabilities", []))
            lines.append(
                f"- **{a['agent_id']}** ({a['name']}): "
                f"[{caps}] | 状态: {a['status']}"
            )
        return "\n".join(lines) if lines else "暂无可用 Agent"

    def _skip_completed_steps(
        self, steps: List[PlanStep], results: Dict[str, Any]
    ) -> List[PlanStep]:
        """跳过已经成功执行的步骤。"""
        remaining = []
        for step in steps:
            output_key = step.output_key or f"step_{step.step}_output"
            if output_key not in results:
                remaining.append(step)
        return remaining

    def get_orchestrator_stats(self) -> Dict[str, Any]:
        """获取编排引擎统计信息。"""
        return {
            "total_plans_generated": self._planning_count,
            "total_replans": self._replan_count,
            "llm_available": self.llm_client is not None,
            "model": self.model,
            "max_replanning": self.max_replanning,
            "registered_agents": len(
                self.harness.registry.list_agents()
            ),
            "quality_loop_enabled": self.enable_quality_loop,
            "quality_checks": self._quality_check_count,
            "quality_failures": self._quality_fail_count,
            "evaluator_stats": self.evaluator.get_stats(),
            "guardrails_stats": self.guardrails.get_stats(),
        }
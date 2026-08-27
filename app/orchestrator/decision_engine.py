"""LLM-Driven Decision Layer: 三层决策架构。

让 Agent 不再是被动执行者，而是主动协作者：
  Perception → Reasoning → Critique → Debate → Decision

三层决策架构：
1. **Strategic Layer (战略层)**: 
   - 目标理解与分解
   - 策略选择与规划
   - 风险评估与预案

2. **Tactical Layer (战术层)**:
   - 工具选择与编排
   - 参数优化
   - 错误恢复

3. **Validation Layer (验证层)**:
   - Critique: 独立评审
   - Debate: 多 Agent 辩论
   - Quality Gate: 质量门禁

Architecture:
    Input
      ↓
    ┌─────────────────────────────────┐
    │  Strategic Decision Layer       │
    │  - Goal Analysis                │
    │  - Strategy Selection           │
    │  - Risk Assessment              │
    └─────────────────────────────────┘
      ↓
    ┌─────────────────────────────────┐
    │  Tactical Decision Layer        │
    │  - Tool Chain Planning          │
    │  - Parameter Optimization       │
    │  - Recovery Strategy            │
    └─────────────────────────────────┘
      ↓
    ┌─────────────────────────────────┐
    │  Validation Layer               │
    │  - Critique (独立评审)          │
    │  - Debate (多Agent辩论)         │
    │  - Quality Gate (质量门禁)      │
    └─────────────────────────────────┘
      ↓
    Output
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data Structures
# ---------------------------------------------------------------------------

class DecisionLayer(Enum):
    STRATEGIC = "strategic"
    TACTICAL = "tactical"
    VALIDATION = "validation"


class DecisionType(Enum):
    GOAL_ANALYSIS = "goal_analysis"
    STRATEGY_SELECTION = "strategy_selection"
    TOOL_CHOICE = "tool_choice"
    PARAMETER_TUNING = "parameter_tuning"
    ERROR_RECOVERY = "error_recovery"
    QUALITY_ASSESSMENT = "quality_assessment"
    DEBATE_RESOLUTION = "debate_resolution"


@dataclass
class DecisionContext:
    """决策上下文。"""
    decision_type: DecisionType
    goal: str
    options: List[Dict[str, Any]] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)
    history: List[Dict[str, Any]] = field(default_factory=list)
    constraints: List[str] = field(default_factory=list)


@dataclass
class DecisionResult:
    """决策结果。"""
    chosen_option: Dict[str, Any]
    reasoning: str
    confidence: float
    alternatives_considered: int
    layer: DecisionLayer
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CritiqueResult:
    """评审结果。"""
    verdict: str  # pass / revise / fail
    scores: Dict[str, float]
    overall_score: float
    issues: List[str]
    suggestions: List[str]
    pass_gate: bool


@dataclass
class DebateResult:
    """辩论结果。"""
    topic: str
    positions: List[Dict[str, Any]]
    consensus: Optional[Dict[str, Any]]
    agreement_level: float  # 0-1
    final_verdict: str


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

STRATEGIC_PROMPT = """你是一个战略决策专家。请分析目标并选择最优策略。

## 目标
{goal}

## 可用策略
{options}

## 上下文
{context}

## 约束条件
{constraints}

## 输出格式
```json
{{
  "analysis": "对目标的深入分析",
  "recommended_strategy": {{
    "strategy_id": "...",
    "reasoning": "选择此策略的原因",
    "expected_benefits": "...",
    "risks": ["风险列表"]
  }},
  "alternatives": [
    {{"strategy_id": "...", "pros": "...", "cons": "..."}}
  ],
  "confidence": 0.0-1.0,
  "fallback_strategy": "降级方案"
}}
```"""

TACTICAL_PROMPT = """你是一个战术决策专家。请为任务选择最优的工具组合和参数。

## 任务目标
{goal}

## 可选工具
{options}

## 当前状态
{context}

## 输出格式
```json
{{
  "tool_chain": [
    {{
      "tool": "工具名",
      "arguments": {{...}},
      "order": 1,
      "reasoning": "选择原因"
    }}
  ],
  "parameter_optimizations": [
    {{
      "tool": "工具名",
      "parameter": "参数名",
      "suggested_value": "...",
      "reasoning": "优化原因"
    }}
  ],
  "recovery_plan": "失败后的恢复策略",
  "confidence": 0.0-1.0
}}
```"""

CRITIQUE_PROMPT = """你是一个严格的评审专家。请审查以下产出物的质量。

## 待审产出
{artifact}

## 原始目标
{goal}

## 评审维度（每项 0-100 分）
1. **准确性 (Accuracy)**: 结果是否正确无误？
2. **完整性 (Completeness)**: 是否覆盖了所有需求？
3. **深度 (Depth)**: 分析是否深入？
4. **可操作性 (Actionability)**: 建议是否可行？
5. **简洁性 (Conciseness)**: 是否冗余？

## 评分标准
- 90+: 优秀，可直接交付
- 70-89: 良好，小修改后可交付
- 50-69: 合格，需要较大改进
- <50: 不合格，需要重做

## 输出格式
```json
{{
  "verdict": "pass|revise|fail",
  "scores": {{
    "accuracy": 0-100,
    "completeness": 0-100,
    "depth": 0-100,
    "actionability": 0-100,
    "conciseness": 0-100
  }},
  "overall_score": 0-100,
  "strengths": ["优点"],
  "issues": ["问题"],
  "suggestions": ["具体改进建议"],
  "pass_gate": true/false,
  "confidence": 0.0-1.0
}}
```"""

DEBATE_PROMPT = """你是一个参与多专家辩论的评审员。请就以下议题给出你的判断。

## 议题
{topic}

## 各方观点
{viewpoints}

## 评审要求
1. 对比各方论据的强弱
2. 识别逻辑漏洞和偏见
3. 综合各方优点，提出建设性结论
4. 明确指出哪些观点更有说服力

## 输出格式
```json
{{
  "comparative_analysis": "对比分析",
  "winning_position": "最有说服力的立场",
  "synthesis": "综合各方优点的结论",
  "confidence": 0.0-1.0,
  "final_verdict": "最终判断",
  "remaining_uncertainties": ["仍存在的不确定性"]
}}
```"""

ERROR_RECOVERY_PROMPT = """你是一个错误恢复专家。请分析错误并给出恢复策略。

## 错误信息
{error}

## 任务上下文
{context}

## 已尝试的方案
{attempts}

## 输出格式
```json
{{
  "error_analysis": "错误根因分析",
  "recovery_options": [
    {{
      "strategy": "恢复策略描述",
      "probability_of_success": 0.0-1.0,
      "cost": "资源消耗评估",
      "steps": ["执行步骤"]
    }}
  ],
  "recommended_strategy": "推荐的恢复策略",
  "should_retry": true/false,
  "should_escalate": true/false
}}
```"""


# ---------------------------------------------------------------------------
# LLM Decision Engine
# ---------------------------------------------------------------------------

class LLMDecisionEngine:
    """LLM 驱动的决策引擎。

    实现三层决策架构，让 Agent 具备主动决策能力：

    1. Strategic: 目标分析、策略选择、风险评估
    2. Tactical: 工具编排、参数优化、错误恢复
    3. Validation: Critique 评审、Debate 辩论、Quality Gate

    Usage:
        engine = LLMDecisionEngine(llm_client)

        # Strategic decision
        result = engine.strategic_decide(
            goal="优化运动训练计划",
            options=[{"id": "a", "desc": "..."}, ...],
            context={"user_profile": {...}}
        )

        # Tactical decision
        result = engine.tactical_decide(
            goal="分析数据",
            tools=["parser", "feature_extractor"],
            context={"data_source": "file.csv"}
        )

        # Validation
        critique = engine.critique(artifact, goal)
        debate = engine.debate(topic, viewpoints)
    """

    def __init__(
        self,
        llm_client: Optional[Any] = None,
        model: str = "gpt-4o-mini",
        quality_threshold: float = 70.0,
        max_debate_rounds: int = 3,
    ):
        self.llm_client = llm_client
        self.model = model
        self.quality_threshold = quality_threshold
        self.max_debate_rounds = max_debate_rounds

        # Decision history
        self._decision_history: List[Dict[str, Any]] = []
        self._critique_history: List[Dict[str, Any]] = []
        self._debate_history: List[Dict[str, Any]] = []

    def strategic_decide(
        self,
        goal: str,
        options: List[Dict[str, Any]],
        context: Optional[Dict[str, Any]] = None,
        constraints: Optional[List[str]] = None,
    ) -> DecisionResult:
        """战略决策：目标分析 + 策略选择。"""
        ctx = context or {}
        cons = constraints or []

        if self.llm_client is None:
            return self._heuristic_strategic(goal, options, ctx, cons)

        prompt = STRATEGIC_PROMPT.format(
            goal=goal,
            options=json.dumps(options, ensure_ascii=False, indent=2),
            context=json.dumps(ctx, ensure_ascii=False, indent=2),
            constraints="\n".join(f"- {c}" for c in cons) or "无特殊约束",
        )

        response = self._call_llm(prompt, f"战略决策: {goal}")
        if response:
            try:
                parsed = json.loads(self._extract_json(response))
                recommended = parsed.get("recommended_strategy", {})
                return DecisionResult(
                    chosen_option=recommended,
                    reasoning=parsed.get("analysis", ""),
                    confidence=parsed.get("confidence", 0.5),
                    alternatives_considered=len(parsed.get("alternatives", [])),
                    layer=DecisionLayer.STRATEGIC,
                    metadata={
                        "fallback": parsed.get("fallback_strategy"),
                        "risks": recommended.get("risks", []),
                    },
                )
            except json.JSONDecodeError:
                pass

        return self._heuristic_strategic(goal, options, ctx, cons)

    def tactical_decide(
        self,
        goal: str,
        tools: List[Dict[str, Any]],
        context: Optional[Dict[str, Any]] = None,
    ) -> DecisionResult:
        """战术决策：工具编排 + 参数优化。"""
        ctx = context or {}

        if self.llm_client is None:
            return self._heuristic_tactical(goal, tools, ctx)

        prompt = TACTICAL_PROMPT.format(
            goal=goal,
            options=json.dumps(tools, ensure_ascii=False, indent=2),
            context=json.dumps(ctx, ensure_ascii=False, indent=2),
        )

        response = self._call_llm(prompt, f"战术决策: {goal}")
        if response:
            try:
                parsed = json.loads(self._extract_json(response))
                return DecisionResult(
                    chosen_option={
                        "tool_chain": parsed.get("tool_chain", []),
                        "parameter_optimizations": parsed.get("parameter_optimizations", []),
                        "recovery_plan": parsed.get("recovery_plan", ""),
                    },
                    reasoning=f"为目标选择 {len(parsed.get('tool_chain', []))} 个工具",
                    confidence=parsed.get("confidence", 0.5),
                    alternatives_considered=len(tools),
                    layer=DecisionLayer.TACTICAL,
                )
            except json.JSONDecodeError:
                pass

        return self._heuristic_tactical(goal, tools, ctx)

    def critique(
        self,
        artifact: Any,
        goal: str,
        dimensions: Optional[List[str]] = None,
    ) -> CritiqueResult:
        """Critique Gate: 独立质量评审。"""
        artifact_str = str(artifact)[:3000] if artifact else "无产出物"

        if self.llm_client is None:
            result = self._heuristic_critique(artifact_str, goal)
            self._critique_history.append({
                "goal": goal,
                "verdict": result.verdict,
                "overall_score": result.overall_score,
                "timestamp": time.time(),
            })
            return result

        prompt = CRITIQUE_PROMPT.format(
            artifact=artifact_str,
            goal=goal,
        )

        response = self._call_llm(prompt, "请进行严格评审")
        if response:
            try:
                parsed = json.loads(self._extract_json(response))
                scores = parsed.get("scores", {})
                overall = parsed.get("overall_score", 50)

                result = CritiqueResult(
                    verdict=parsed.get("verdict", "revise"),
                    scores=scores,
                    overall_score=overall,
                    issues=parsed.get("issues", []),
                    suggestions=parsed.get("suggestions", []),
                    pass_gate=parsed.get("pass_gate", overall >= self.quality_threshold),
                )
                self._critique_history.append({
                    "goal": goal,
                    "verdict": result.verdict,
                    "overall_score": overall,
                    "timestamp": time.time(),
                })
                return result
            except json.JSONDecodeError:
                pass

        return self._heuristic_critique(artifact_str, goal)

    def debate(
        self,
        topic: str,
        viewpoints: List[Dict[str, Any]],
        roles: Optional[List[str]] = None,
    ) -> DebateResult:
        """Multi-Agent Debate: 多 Agent 辩论。"""
        if self.llm_client is None or len(viewpoints) < 2:
            result = DebateResult(
                topic=topic,
                positions=viewpoints,
                consensus=viewpoints[0] if viewpoints else None,
                agreement_level=0.5,
                final_verdict="信息不足，无法进行有意义的辩论",
            )
            self._debate_history.append({
                "topic": topic,
                "viewpoints_count": len(viewpoints),
                "agreement_level": result.agreement_level,
                "timestamp": time.time(),
            })
            return result

        prompt = DEBATE_PROMPT.format(
            topic=topic,
            viewpoints=json.dumps(viewpoints, ensure_ascii=False, indent=2),
        )

        # Multi-round debate
        last_result = None
        for round_idx in range(self.max_debate_rounds):
            response = self._call_llm(
                prompt,
                f"辩论第 {round_idx + 1} 轮: {topic}",
            )
            if response:
                try:
                    parsed = json.loads(self._extract_json(response))
                    last_result = DebateResult(
                        topic=topic,
                        positions=viewpoints,
                        consensus=parsed.get("synthesis", {}),
                        agreement_level=parsed.get("confidence", 0.5),
                        final_verdict=parsed.get("final_verdict", ""),
                    )

                    # If high confidence, stop early
                    if last_result.agreement_level >= 0.8:
                        break

                    # Update prompt with previous round's synthesis
                    prompt += f"\n\n## 上一轮结论\n{parsed.get('synthesis', '')}"
                except json.JSONDecodeError:
                    break

        if last_result is None:
            last_result = DebateResult(
                topic=topic,
                positions=viewpoints,
                consensus=viewpoints[0] if viewpoints else None,
                agreement_level=0.3,
                final_verdict="辩论未能达成有效结论",
            )

        self._debate_history.append({
            "topic": topic,
            "viewpoints_count": len(viewpoints),
            "agreement_level": last_result.agreement_level,
            "timestamp": time.time(),
        })
        return last_result

    def error_recovery(
        self,
        error: str,
        context: Dict[str, Any],
        attempts: int = 0,
    ) -> DecisionResult:
        """错误恢复决策。"""
        if self.llm_client is None:
            return self._heuristic_recovery(error, context, attempts)

        prompt = ERROR_RECOVERY_PROMPT.format(
            error=error,
            context=json.dumps(context, ensure_ascii=False, indent=2),
            attempts=f"已尝试 {attempts} 次",
        )

        response = self._call_llm(prompt, "请分析错误并给出恢复策略")
        if response:
            try:
                parsed = json.loads(self._extract_json(response))
                options = parsed.get("recovery_options", [])
                best = max(options, key=lambda o: o.get("probability_of_success", 0)) if options else {}

                return DecisionResult(
                    chosen_option={
                        "strategy": parsed.get("recommended_strategy", ""),
                        "options": options,
                        "should_retry": parsed.get("should_retry", False),
                        "should_escalate": parsed.get("should_escalate", False),
                    },
                    reasoning=parsed.get("error_analysis", ""),
                    confidence=best.get("probability_of_success", 0.5) if best else 0.3,
                    alternatives_considered=len(options),
                    layer=DecisionLayer.TACTICAL,
                )
            except json.JSONDecodeError:
                pass

        return self._heuristic_recovery(error, context, attempts)

    # ------------------------------------------------------------------
    # Heuristic Fallbacks (no LLM)
    # ------------------------------------------------------------------

    def _heuristic_strategic(
        self,
        goal: str,
        options: List[Dict[str, Any]],
        context: Dict,
        constraints: List[str],
    ) -> DecisionResult:
        """启发式战略决策。"""
        if not options:
            return DecisionResult(
                chosen_option={},
                reasoning="无可用策略",
                confidence=0.0,
                alternatives_considered=0,
                layer=DecisionLayer.STRATEGIC,
            )

        # Score options based on keyword matching
        best = max(options, key=lambda o: self._score_option(o, goal))
        return DecisionResult(
            chosen_option=best,
            reasoning=f"基于关键词匹配选择最优策略: {best.get('id', 'unknown')}",
            confidence=0.5,
            alternatives_considered=len(options),
            layer=DecisionLayer.STRATEGIC,
        )

    def _heuristic_tactical(
        self,
        goal: str,
        tools: List[Dict[str, Any]],
        context: Dict,
    ) -> DecisionResult:
        """启发式战术决策。"""
        if not tools:
            return DecisionResult(
                chosen_option={"tool_chain": []},
                reasoning="无可用工具",
                confidence=0.0,
                alternatives_considered=0,
                layer=DecisionLayer.TACTICAL,
            )

        # Select tools whose descriptions match the goal
        relevant = [
            t for t in tools
            if any(kw in str(t.get("description", "")).lower() for kw in goal.lower().split())
        ]
        if not relevant:
            relevant = tools[:2]  # Fallback: take first 2

        return DecisionResult(
            chosen_option={
                "tool_chain": [
                    {"tool": t.get("name", ""), "arguments": {}, "order": i + 1}
                    for i, t in enumerate(relevant)
                ],
                "recovery_plan": "按顺序执行，失败则跳过",
            },
            reasoning=f"选择 {len(relevant)} 个相关工具",
            confidence=0.4,
            alternatives_considered=len(tools),
            layer=DecisionLayer.TACTICAL,
        )

    def _heuristic_critique(
        self,
        artifact: str,
        goal: str,
    ) -> CritiqueResult:
        """启发式评审。"""
        if not artifact or len(artifact.strip()) < 10:
            return CritiqueResult(
                verdict="fail",
                scores={"accuracy": 30, "completeness": 20, "depth": 10,
                        "actionability": 10, "conciseness": 50},
                overall_score=24,
                issues=["产出物为空或过短"],
                suggestions=["重新生成产出物"],
                pass_gate=False,
            )

        # Simple heuristic: length-based scoring
        length_score = min(100, len(artifact) / 20)
        return CritiqueResult(
            verdict="pass" if length_score >= self.quality_threshold else "revise",
            scores={
                "accuracy": length_score,
                "completeness": length_score * 0.9,
                "depth": length_score * 0.8,
                "actionability": length_score * 0.7,
                "conciseness": min(100, 100 - len(artifact) / 100),
            },
            overall_score=length_score * 0.8,
            issues=[] if length_score >= self.quality_threshold else ["产出物可能不够详细"],
            suggestions=["增加更多细节"] if length_score < self.quality_threshold else [],
            pass_gate=length_score >= self.quality_threshold,
        )

    def _heuristic_recovery(
        self,
        error: str,
        context: Dict,
        attempts: int,
    ) -> DecisionResult:
        """启发式错误恢复。"""
        is_retryable = any(kw in error.lower() for kw in [
            "timeout", "network", "temporary", "retry", "connection"
        ])

        return DecisionResult(
            chosen_option={
                "strategy": "重试" if is_retryable else "跳过并报告",
                "should_retry": is_retryable and attempts < 3,
                "should_escalate": not is_retryable or attempts >= 3,
            },
            reasoning=f"错误类型分析: {'可重试' if is_retryable else '需要升级'}",
            confidence=0.6 if is_retryable else 0.3,
            alternatives_considered=2,
            layer=DecisionLayer.TACTICAL,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _score_option(self, option: Dict, goal: str) -> float:
        """评分选项与目标的匹配度。"""
        score = 0.0
        goal_words = set(goal.lower().split())
        option_text = json.dumps(option).lower()
        for word in goal_words:
            if word in option_text:
                score += 1.0
        return score / max(len(goal_words), 1)

    def _call_llm(self, system_prompt: str, user_message: str) -> Optional[str]:
        """调用 LLM。"""
        if self.llm_client is None:
            return None

        try:
            response = self.llm_client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                temperature=0.2,
                max_tokens=2000,
            )
            return response.choices[0].message.content.strip()
        except Exception as exc:
            logger.warning("LLM call failed: %s", exc)
            return None

    def _extract_json(self, text: str) -> str:
        """从 LLM 响应中提取 JSON。"""
        text = text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1] == "```":
                lines = lines[:-1]
            text = "\n".join(lines)
        return text.strip()

    def get_stats(self) -> Dict[str, Any]:
        """获取决策引擎统计。"""
        return {
            "model": self.model,
            "quality_threshold": self.quality_threshold,
            "max_debate_rounds": self.max_debate_rounds,
            "total_decisions": len(self._decision_history),
            "total_critiques": len(self._critique_history),
            "total_debates": len(self._debate_history),
            "critique_pass_rate": (
                sum(1 for c in self._critique_history if c.get("verdict") == "pass")
                / max(len(self._critique_history), 1) * 100
            ),
        }
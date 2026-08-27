"""EvaluatorAgent: Agent 产出质量评估器。

核心价值：
1. 多维度评估：从准确性、完整性、相关性、格式规范性等角度评估产出
2. 量化评分：每个维度给出 0-10 分的量化指标
3. 反馈闭环：生成具体的改进建议，供上游 Agent 参考
4. 阈值控制：低于质量阈值时触发重新生成或降级

面试展示点：
- 展示了对 Agent 输出质量的系统性思考
- 体现了"Agent 不仅仅是生成，还要能自我评估"的工程理念
- 评估维度设计体现了真实业务场景的质量要求

Architecture:
    Agent Output → [EvaluatorAgent] → Score Card → Feedback → [Upstream Agent]
                                        ↓
                              Below Threshold → Retry / Fallback
"""

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 评估维度定义
# ---------------------------------------------------------------------------

@dataclass
class EvaluationDimension:
    """单个评估维度。"""
    name: str
    weight: float  # 权重 0-1
    score: float = 0.0  # 分数 0-10
    comment: str = ""


@dataclass
class EvaluationResult:
    """完整的评估结果。"""
    overall_score: float = 0.0  # 加权总分
    dimensions: List[EvaluationDimension] = field(default_factory=list)
    passed: bool = False
    threshold: float = 6.0  # 及格阈值
    feedback: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    evaluated_at: float = field(default_factory=time.time)
    evaluator_name: str = "EvaluatorAgent"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "overall_score": self.overall_score,
            "passed": self.passed,
            "threshold": self.threshold,
            "dimensions": [
                {
                    "name": d.name,
                    "weight": d.weight,
                    "score": d.score,
                    "comment": d.comment,
                }
                for d in self.dimensions
            ],
            "feedback": self.feedback,
            "suggestions": self.suggestions,
            "evaluated_at": self.evaluated_at,
            "evaluator": self.evaluator_name,
        }


# ---------------------------------------------------------------------------
# 内置评估规则
# ---------------------------------------------------------------------------

class BuiltinEvaluationRules:
    """内置评估规则集合。

    针对运动分析场景，定义了以下评估维度：
    1. 准确性：数据是否准确，建议是否基于事实
    2. 完整性：是否覆盖了用户的所有问题
    3. 可操作性：建议是否具体、可执行
    4. 专业性：术语使用是否规范
    5. 个性化：是否考虑了用户的历史数据和偏好
    """

    @staticmethod
    def get_default_dimensions() -> List[EvaluationDimension]:
        """获取默认评估维度。"""
        return [
            EvaluationDimension(
                name="准确性",
                weight=0.3,
                comment="评估数据引用是否准确，建议是否基于运动科学原理",
            ),
            EvaluationDimension(
                name="完整性",
                weight=0.25,
                comment="评估是否覆盖了用户的所有问题点",
            ),
            EvaluationDimension(
                name="可操作性",
                weight=0.2,
                comment="评估建议是否具体、可执行，而非空泛",
            ),
            EvaluationDimension(
                name="专业性",
                weight=0.15,
                comment="评估术语使用是否规范，是否符合运动科学标准",
            ),
            EvaluationDimension(
                name="个性化",
                weight=0.1,
                comment="评估是否考虑了用户的历史数据和个体差异",
            ),
        ]

    @staticmethod
    def quick_evaluate(
        output: str,
        goal: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> EvaluationResult:
        """快速规则评估（无需 LLM）。

        Args:
            output: Agent 产出文本
            goal: 原始目标
            context: 上下文信息

        Returns:
            评估结果
        """
        dimensions = BuiltinEvaluationRules.get_default_dimensions()
        feedback = []
        suggestions = []

        # 1. 准确性评估
        # 检查是否包含数据引用
        has_numbers = any(c.isdigit() for c in output)
        has_units = any(
            unit in output
            for unit in ["km", "min", "秒", "bpm", "次", "%,", "kcal"]
        )
        if has_numbers and has_units:
            dimensions[0].score = 8.0
            dimensions[0].comment = "包含具体数据和单位，准确性较好"
        elif has_numbers:
            dimensions[0].score = 6.0
            dimensions[0].comment = "包含数据但缺少单位"
            feedback.append("建议添加数据单位以提高准确性")
        else:
            dimensions[0].score = 4.0
            dimensions[0].comment = "缺少具体数据支撑"
            feedback.append("建议引用具体数据来支撑结论")
            suggestions.append("在建议中加入具体数字（如配速、心率、距离）")

        # 2. 完整性评估
        goal_keywords = [w for w in goal.split() if len(w) > 1]
        covered = sum(1 for kw in goal_keywords if kw in output)
        if goal_keywords:
            coverage = covered / len(goal_keywords)
            dimensions[1].score = coverage * 10
            dimensions[1].comment = f"目标覆盖率: {coverage:.0%}"
            if coverage < 0.5:
                feedback.append(f"未充分覆盖目标: {goal}")
                suggestions.append("确保回答覆盖用户的所有问题点")

        # 3. 可操作性评估
        action_words = ["应该", "建议", "可以", "需要", "尝试", "推荐", "最佳"]
        has_actions = any(w in output for w in action_words)
        action_count = sum(1 for w in action_words if w in output)
        if has_actions and action_count >= 2:
            dimensions[2].score = 8.0
            dimensions[2].comment = "包含多个可操作建议"
        elif has_actions:
            dimensions[2].score = 6.0
            dimensions[2].comment = "包含建议但不够具体"
            feedback.append("建议可以更具体")
        else:
            dimensions[2].score = 3.0
            dimensions[2].comment = "缺少具体建议"
            feedback.append("需要提供具体的行动建议")
            suggestions.append("使用'你应该...'、'建议...'等句式给出具体建议")

        # 4. 专业性评估
        professional_terms = [
            "配速", "心率区间", "训练负荷", "VO2max", "Lactate",
            "阈值", "周期化", "恢复", "过度训练", "间歇",
        ]
        term_count = sum(1 for t in professional_terms if t.lower() in output.lower())
        if term_count >= 2:
            dimensions[3].score = 8.0
            dimensions[3].comment = f"使用了 {term_count} 个专业术语"
        elif term_count >= 1:
            dimensions[3].score = 6.0
            dimensions[3].comment = "使用了少量专业术语"
        else:
            dimensions[3].score = 5.0
            dimensions[3].comment = "缺少专业术语"
            suggestions.append("适当使用运动科学术语以增强专业性")

        # 5. 个性化评估
        if context and context.get("user_profile"):
            profile = context.get("user_profile", {})
            profile_items = str(profile)
            if any(kw in output for kw in profile_items.split()[:5]):
                dimensions[4].score = 8.0
                dimensions[4].comment = "引用了用户历史数据"
            else:
                dimensions[4].score = 5.0
                dimensions[4].comment = "未充分引用用户数据"
        else:
            dimensions[4].score = 6.0
            dimensions[4].comment = "无用户上下文，默认分"

        # 计算加权总分
        total_weight = sum(d.weight for d in dimensions)
        overall = sum(d.score * d.weight for d in dimensions) / total_weight if total_weight > 0 else 0

        return EvaluationResult(
            overall_score=round(overall, 2),
            dimensions=dimensions,
            passed=overall >= 6.0,
            threshold=6.0,
            feedback=feedback,
            suggestions=suggestions,
        )


# ---------------------------------------------------------------------------
# EvaluatorAgent 主实现
# ---------------------------------------------------------------------------

class EvaluatorAgent(BaseAgent):
    """Agent 产出质量评估器。

    支持两种评估模式：
    1. 规则评估：无需 LLM，基于关键词和模式匹配，快速但简单
    2. LLM 评估：调用 LLM 进行语义理解，更准确但需要 API

    评估流程：
    1. 接收待评估的产出和原始目标
    2. 执行多维度评估
    3. 生成量化评分和改进建议
    4. 返回评估结果（含是否通过阈值）

    Usage:
        evaluator = EvaluatorAgent()
        result = evaluator.evaluate(
            output="你的配速是5:30/km...",
            goal="分析我的跑步数据",
            context={"user_profile": {...}},
        )
        if not result.passed:
            print(result.suggestions)
    """

    agent_id = "evaluator"
    agent_name = "Output Quality Evaluator"
    capabilities = ["quality_assessment", "scoring", "feedback_generation"]
    MAX_HISTORY = 50

    def __init__(
        self,
        llm_enabled: bool = False,
        model: str = "gpt-4o-mini",
        trace_collector=None,
    ) -> None:
        super().__init__(name="evaluator_agent", trace_collector=trace_collector)
        self.llm_enabled = llm_enabled
        self.model = model
        self._evaluation_count = 0
        self._pass_count = 0
        self._total_score = 0.0
        self._evaluation_history: List[Dict[str, Any]] = []

    def run(
        self,
        output: str,
        goal: str,
        context: Optional[Dict[str, Any]] = None,
        session_id: str = "default",
    ) -> Dict[str, Any]:
        """评估 Agent 产出质量。

        Args:
            output: 待评估的产出文本
            goal: 原始目标
            context: 上下文信息
            session_id: 会话标识

        Returns:
            {
                "success": bool,
                "evaluation": {...},  # EvaluationResult.to_dict()
                "passed": bool,
                "score": float,
                "suggestions": [...],
            }
        """
        self._execution_count += 1
        self._last_input = output[:200]

        self._trace_step(
            session_id=session_id,
            step_type="thought",
            thought=f"开始评估产出质量",
            detail={
                "output_length": len(output),
                "goal": goal[:100],
                "llm_enabled": self.llm_enabled,
            },
        )

        # 执行评估（evaluate 内部已处理统计）
        result = self.evaluate(output, goal, context)

        self._trace_step(
            session_id=session_id,
            step_type="final",
            thought=f"评估完成: {result.overall_score}/10 {'通过' if result.passed else '未通过'}",
            detail={
                "score": result.overall_score,
                "passed": result.passed,
                "dimensions_count": len(result.dimensions),
                "suggestions_count": len(result.suggestions),
            },
        )

        return {
            "success": True,
            "evaluation": result.to_dict(),
            "passed": result.passed,
            "score": result.overall_score,
            "suggestions": result.suggestions,
        }

    def evaluate(
        self,
        output: str,
        goal: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> EvaluationResult:
        """执行评估（支持规则 + LLM 两种模式）。

        Args:
            output: 待评估文本
            goal: 原始目标
            context: 上下文

        Returns:
            评估结果
        """
        if self.llm_enabled:
            # LLM 评估（降级到规则评估）
            try:
                result = self._llm_evaluate(output, goal, context)
            except Exception as exc:
                logger.warning("LLM evaluation failed, falling back to rules: %s", exc)
                result = BuiltinEvaluationRules.quick_evaluate(output, goal, context)
        else:
            result = BuiltinEvaluationRules.quick_evaluate(output, goal, context)

        # 更新统计
        self._evaluation_count += 1
        self._total_score += result.overall_score
        if result.passed:
            self._pass_count += 1

        # 存储历史
        self._evaluation_history.append({
            "output_length": len(output),
            "goal": goal[:100],
            "score": result.overall_score,
            "passed": result.passed,
        })
        if len(self._evaluation_history) > self.MAX_HISTORY:
            self._evaluation_history = self._evaluation_history[-self.MAX_HISTORY:]

        return result

    def _llm_evaluate(
        self,
        output: str,
        goal: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> EvaluationResult:
        """使用 LLM 进行语义级评估。

        Args:
            output: 待评估文本
            goal: 原始目标
            context: 上下文

        Returns:
            评估结果
        """
        from openai import OpenAI
        import os

        api_key = os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            return BuiltinEvaluationRules.quick_evaluate(output, goal, context)

        client = OpenAI(api_key=api_key)

        prompt = f"""请评估以下 Agent 产出的质量。

## 原始目标
{goal}

## 产出内容
{output[:2000]}

## 评估维度（每个维度 0-10 分）
1. 准确性：数据是否准确，建议是否基于事实
2. 完整性：是否覆盖了所有问题点
3. 可操作性：建议是否具体可执行
4. 专业性：术语使用是否规范
5. 个性化：是否考虑了用户个体差异

## 输出格式（JSON）
{{
  "scores": {{
    "准确性": 0-10,
    "完整性": 0-10,
    "可操作性": 0-10,
    "专业性": 0-10,
    "个性化": 0-10
  }},
  "overall_score": 0-10,
  "passed": true/false,
  "suggestions": ["改进建议1", "改进建议2"],
  "reasoning": "评估理由"
}}"""

        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "你是一个严格的质量评估专家。"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            max_tokens=1000,
        )

        # 解析 LLM 响应
        try:
            content = response.choices[0].message.content.strip()
            if content.startswith("```"):
                content = content.split("\n", 1)[-1] if "\n" in content else content[3:]
                content = content.rsplit("```", 1)[0]

            data = json.loads(content)
            dimensions = BuiltinEvaluationRules.get_default_dimensions()

            # 填充 LLM 评分
            for dim in dimensions:
                if dim.name in data.get("scores", {}):
                    dim.score = float(data["scores"][dim.name])
                    dim.comment = f"LLM评分: {dim.score}/10"

            return EvaluationResult(
                overall_score=float(data.get("overall_score", 0)),
                dimensions=dimensions,
                passed=bool(data.get("passed", False)),
                threshold=6.0,
                feedback=data.get("reasoning", ""),
                suggestions=data.get("suggestions", []),
                evaluator_name="EvaluatorAgent (LLM)",
            )
        except (json.JSONDecodeError, KeyError) as exc:
            logger.warning("Failed to parse LLM evaluation: %s", exc)
            return BuiltinEvaluationRules.quick_evaluate(output, goal, context)

    def get_stats(self) -> Dict[str, Any]:
        """获取评估统计信息。"""
        return {
            "total_evaluations": self._evaluation_count,
            "pass_rate": (self._pass_count / self._evaluation_count * 100)
            if self._evaluation_count > 0
            else 0,
            "average_score": (self._total_score / self._evaluation_count)
            if self._evaluation_count > 0
            else 0,
            "llm_enabled": self.llm_enabled,
            "history_count": len(self._evaluation_history),
        }

    def get_recent_evaluations(self, limit: int = 10) -> List[Dict[str, Any]]:
        """获取最近的评估记录。"""
        return self._evaluation_history[-limit:]

    def reset_stats(self) -> None:
        """重置统计。"""
        self._evaluation_count = 0
        self._pass_count = 0
        self._total_score = 0.0

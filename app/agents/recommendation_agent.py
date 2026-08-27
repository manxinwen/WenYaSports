"""RecommendationAgent: rule engine + optional LLM hybrid.

Rule results always win for recovery_days / training_zones; the LLM only
generates natural-language suggestion text, with graceful fallback.
"""

import json
import logging
import os
from typing import Optional

from openai import OpenAI

from app.agents.base_agent import BaseAgent
from app.models.features import ActivityFeatures
from app.models.recommendation import LLMRecommendationOutput, Recommendation
from app.services.recommendation_rules import apply_rules

logger = logging.getLogger(__name__)

_LLM_MODEL = "gpt-4o-mini"

_SYSTEM_PROMPT = (
    "你是一位专业的运动训练教练，精通跑步、骑行等耐力运动训练安排。"
    "请根据用户的活动数据和用户画像，用简洁、专业、可执行的中文给出训练建议。"
    "只输出一个JSON对象，格式为 {\"suggestion_text\": \"建议内容\"}。"
)


class RecommendationAgent(BaseAgent):
    """Generates training recommendations based on features and user profile.

    Supports Harness integration for:
    - Trace recording for observability
    - Message-based communication with other agents
    - Blackboard data sharing
    """

    agent_id = "recommender"
    agent_name = "Recommendation Engine"
    capabilities = ["training_advice", "rule_engine", "llm_generation"]

    def __init__(self, llm_enabled: bool = True, openai_api_key: Optional[str] = None, name: Optional[str] = None, trace_collector=None):
        super().__init__(name=name, trace_collector=trace_collector)
        self.llm_enabled = llm_enabled
        self.openai_api_key = openai_api_key or os.environ.get("OPENAI_API_KEY")

    def run(
        self,
        features: ActivityFeatures,
        user_profile: dict,
        short_term_context: dict,
    ) -> Recommendation:
        self._execution_count += 1
        self._last_input = f"Features: load={features.training_load:.1f}"

        self._trace_step(
            step_type="thought",
            thought=f"分析活动特征，生成训练建议",
            detail={
                "training_load": features.training_load,
                "intensity": features.intensity_distribution,
                "has_user_profile": bool(user_profile),
            },
        )

        self._trace_step(
            step_type="action",
            thought="执行规则引擎评估",
            detail={"rules": ["recovery_days", "training_zones"]},
        )

        rules = apply_rules(features, user_profile)
        recovery_days = rules["recovery_days"]
        training_zones = rules["training_zones"]

        self._trace_step(
            step_type="observation",
            thought=f"规则引擎结果: 恢复{recovery_days}天, 训练区间={training_zones}",
            detail=rules,
        )

        suggestion_text = rules["rule_based_suggestion"]
        if self.llm_enabled and self.openai_api_key:
            self._trace_step(
                step_type="action",
                thought="调用 LLM 生成自然语言建议",
                detail={"model": _LLM_MODEL},
            )
            suggestion_text = self._generate_with_llm(
                features, user_profile, short_term_context, rules
            )

        result = Recommendation(
            suggestion_text=suggestion_text,
            recovery_days=recovery_days,
            training_zones=training_zones,
        )
        self._last_output = result

        if self.blackboard:
            self.write_to_blackboard(
                namespace="recommendation_results",
                key=f"recommendation_{self._execution_count}",
                value={
                    "recovery_days": recovery_days,
                    "training_zones": training_zones,
                    "suggestion_length": len(suggestion_text),
                },
            )

        self._trace_step(
            step_type="final",
            thought=f"建议生成完成: {recovery_days}天恢复, {training_zones}区间",
            detail={
                "recovery_days": recovery_days,
                "training_zones": training_zones,
                "suggestion_preview": suggestion_text[:100] if suggestion_text else "",
            },
        )

        if self.message_bus:
            self.broadcast_message(
                message_type="agent_completed",
                payload={
                    "agent_id": self.agent_id,
                    "status": "success",
                    "output_summary": f"Rest={recovery_days}d, Zones={training_zones}",
                },
            )

        return result

    def _build_prompt(
        self, features: ActivityFeatures, user_profile: dict, short_term_context: dict, rules: dict
    ) -> str:
        feature_summary = {
            "运动时长秒": features.total_duration_seconds,
            "距离米": features.total_distance_m,
            "平均心率": features.avg_hr,
            "最大心率": features.max_hr,
            "心率区间占比": features.hr_zones,
            "平均配速分钟每公里": features.avg_pace_min_per_km,
            "累计爬升米": features.elevation_gain_m,
            "训练负荷": features.training_load,
            "是否为间歇训练": features.interval_training,
            "强度类型": features.intensity_distribution,
        }
        return json.dumps(
            {
                "活动特征": feature_summary,
                "用户画像": user_profile,
                "短期上下文": short_term_context,
                "规则引擎结果": {
                    "恢复天数": rules["recovery_days"],
                    "建议训练区间": rules["training_zones"],
                },
            },
            ensure_ascii=False,
        )

    def _generate_with_llm(
        self,
        features: ActivityFeatures,
        user_profile: dict,
        short_term_context: dict,
        rules: dict,
    ) -> str:
        prompt = self._build_prompt(features, user_profile, short_term_context, rules)
        try:
            client = OpenAI(api_key=self.openai_api_key)
            resp = client.chat.completions.create(
                model=_LLM_MODEL,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
                response_format={"type": "json_object"},
            )
            content = resp.choices[0].message.content
            parsed = LLMRecommendationOutput.model_validate_json(content)
            return parsed.suggestion_text.strip()
        except Exception as exc:
            logger.warning("LLM推荐生成失败，降级为规则建议: %s", exc)
            return rules["rule_based_suggestion"]

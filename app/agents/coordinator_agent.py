"""CoordinatorAgent: orchestrates the multi-agent pipeline.

Parser -> FeatureExtractor -> Memory -> Recommendation -> Memory update
"""

import logging
from typing import Optional

from app.agents.base_agent import BaseAgent
from app.models.activity import ParsedActivity
from app.models.features import ActivityFeatures
from app.models.recommendation import Recommendation
from app.services.fit_parser import FitParseError

logger = logging.getLogger(__name__)


class CoordinatorError(Exception):
    """Raised when the pipeline fails; carries an HTTP status code."""

    def __init__(self, message: str, status_code: int = 500):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class CoordinatorAgent(BaseAgent):
    """Orchestrates parsing, feature extraction, memory and recommendation."""

    def __init__(self, parser_agent, feature_agent, memory_agent, recommendation_agent):
        self.parser_agent = parser_agent
        self.feature_agent = feature_agent
        self.memory_agent = memory_agent
        self.recommendation_agent = recommendation_agent

    def run(self, file_path: str, user_id: str, session_id: str) -> dict:
        # 1. Parse + feature extraction (hard dependencies)
        try:
            activity = self.parser_agent.run(file_path)
            features = self.feature_agent.run(activity)
        except FitParseError as exc:
            logger.error("FIT文件解析失败: %s", exc)
            raise CoordinatorError(str(exc), status_code=400) from exc
        except Exception as exc:
            logger.exception("解析或特征提取失败")
            raise CoordinatorError(f"处理活动数据失败: {exc}", status_code=500) from exc

        # 2. Memory context (degradable -> empty profile)
        user_profile: dict = {}
        short_term_context: dict = {}
        try:
            context = self.memory_agent.get_context(user_id, session_id) or {}
            user_profile = context.get("user_profile") or {}
            short_term_context = context.get("short_term_context") or {}
            if "recent_load_7d" in context:
                user_profile = {**user_profile, "recent_load_7d": context["recent_load_7d"]}
        except Exception:
            logger.exception("获取记忆上下文失败，降级为空画像")

        # 3. Recommendation (degradable -> partial result with warning)
        warning: Optional[str] = None
        recommendation: Optional[Recommendation] = None
        try:
            recommendation = self.recommendation_agent.run(
                features, user_profile, short_term_context
            )
        except Exception as exc:
            logger.exception("推荐生成失败，返回部分结果")
            warning = f"推荐生成失败: {exc}"

        # 4. Update memory (best effort)
        try:
            if recommendation is not None:
                self.memory_agent.update(
                    user_id,
                    session_id,
                    features,
                    recommendation,
                    metadata=activity.metadata.model_dump(mode="json"),
                    file_path=file_path,
                )
        except Exception:
            logger.exception("记忆更新失败")

        result = {
            "activity_metadata": activity.metadata.model_dump(),
            "activity_features": features.model_dump(),
            "recommendation": recommendation.model_dump() if recommendation else None,
            "user_profile_summary": user_profile,
        }
        if warning:
            result["warning"] = warning
        return result

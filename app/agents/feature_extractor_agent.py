"""FeatureExtractorAgent: computes ActivityFeatures from a ParsedActivity."""

from app.agents.base_agent import BaseAgent
from app.models.activity import ParsedActivity
from app.models.features import ActivityFeatures
from app.services.feature_engine import compute_features


class FeatureExtractorAgent(BaseAgent):
    """Computes training features from parsed activity data."""

    def run(self, activity: ParsedActivity) -> ActivityFeatures:
        data = compute_features(activity.records, activity.metadata)
        return ActivityFeatures(**data)

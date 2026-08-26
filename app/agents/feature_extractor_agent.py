"""FeatureExtractorAgent: computes ActivityFeatures from a ParsedActivity."""

import logging

from app.agents.base_agent import BaseAgent
from app.models.activity import ParsedActivity
from app.models.features import ActivityFeatures
from app.services.feature_engine import compute_features

logger = logging.getLogger(__name__)


class FeatureExtractorAgent(BaseAgent):
    """Computes training features from parsed activity data.

    Supports Harness integration for:
    - Trace recording for observability
    - Message-based communication with other agents
    - Blackboard data sharing
    """

    agent_id = "feature_extractor"
    agent_name = "Feature Extractor"
    capabilities = ["feature_engineering", "statistics", "intensity_distribution"]

    def run(self, activity: ParsedActivity) -> ActivityFeatures:
        self._execution_count += 1
        self._last_input = f"ParsedActivity: {activity.metadata.total_distance_m:.1f}m"

        self._trace_step(
            step_type="thought",
            thought=f"开始提取特征: {activity.metadata.total_distance_m:.1f}m, {len(activity.records)} 条记录",
            detail={
                "records_count": len(activity.records),
                "sport": activity.metadata.sport,
            },
        )

        self._trace_step(
            step_type="action",
            thought="调用特征计算引擎",
            detail={
                "computing": [
                    "distance", "duration", "elevation",
                    "heart_rate_zones", "speed_stats"
                ],
            },
        )

        data = compute_features(activity.records, activity.metadata)
        result = ActivityFeatures(**data)
        self._last_output = result

        if self.blackboard:
            self.write_to_blackboard(
                namespace="feature_extractor_results",
                key=f"features_{self._execution_count}",
                value={
                    "total_distance_m": result.total_distance_m,
                    "total_duration_seconds": result.total_duration_seconds,
                    "avg_hr": result.avg_hr,
                    "training_load": result.training_load,
                    "intensity_distribution": result.intensity_distribution,
                },
            )

        self._trace_step(
            step_type="final",
            thought=f"特征提取完成: 负荷={result.training_load:.1f}, 强度分布={result.intensity_distribution}",
            detail={
                "training_load": result.training_load,
                "avg_hr": result.avg_hr,
                "intensity_distribution": result.intensity_distribution,
                "hr_zones": result.hr_zones,
            },
        )

        if self.message_bus:
            self.broadcast_message(
                message_type="agent_completed",
                payload={
                    "agent_id": self.agent_id,
                    "status": "success",
                    "output_summary": f"Load={result.training_load:.1f}",
                },
            )

        return result

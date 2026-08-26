from datetime import datetime, timedelta
from unittest import mock

import pytest

from app.agents.coordinator_agent import CoordinatorAgent, CoordinatorError
from app.models.activity import ActivityMetadata, ActivityRecord, ParsedActivity
from app.models.features import ActivityFeatures
from app.models.recommendation import Recommendation
from app.services.fit_parser import FitParseError


def make_activity():
    return ParsedActivity(
        metadata=ActivityMetadata(
            sport="running",
            start_time=datetime(2026, 1, 1, 8, 0, 0),
            total_duration_s=3600.0,
            total_distance_m=10000.0,
            total_ascent_m=100.0,
            total_descent_m=50.0,
            avg_hr=150.0,
            max_hr=180,
            avg_speed=2.78,
            max_speed=5.0,
        ),
        records=[
            ActivityRecord(
                timestamp=datetime(2026, 1, 1, 8, 0, 0) + timedelta(seconds=i),
                hr=150,
                speed=2.78,
            )
            for i in range(10)
        ],
    )


def make_features():
    return ActivityFeatures(
        total_duration_seconds=3600.0,
        total_distance_m=10000.0,
        avg_hr=150.0,
        max_hr=180,
        hr_zones={"zone1": 0.0, "zone2": 50.0, "zone3": 50.0, "zone4": 0.0, "zone5": 0.0},
        avg_pace_min_per_km=6.0,
        elevation_gain_m=100.0,
        training_load=180.0,
        interval_training=False,
        intensity_distribution="tempo",
    )


def make_recommendation():
    return Recommendation(
        suggestion_text="建议进行轻松跑恢复",
        recovery_days=1,
        training_zones={"hr_zone": "Z2", "pace_range": "6:00-6:30 min/km"},
    )


def test_coordinator_calls_agents_in_order():
    activity = make_activity()
    features = make_features()
    recommendation = make_recommendation()

    parser = mock.MagicMock()
    parser.run.return_value = activity
    feature_agent = mock.MagicMock()
    feature_agent.run.return_value = features
    memory = mock.MagicMock()
    memory.get_context.return_value = {
        "user_profile": {"fitness_level": "beginner"},
        "recent_load_7d": 120,
        "short_term_context": {"note": "recently did intervals"},
    }
    rec_agent = mock.MagicMock()
    rec_agent.run.return_value = recommendation

    coord = CoordinatorAgent(parser, feature_agent, memory, rec_agent)
    result = coord.run("x.fit", "user1", "sess1")

    parser.run.assert_called_once_with("x.fit")
    feature_agent.run.assert_called_once_with(activity)
    memory.get_context.assert_called_once_with("user1", "sess1")

    # user_profile passed to rec agent includes merged recent_load_7d
    args, _ = rec_agent.run.call_args
    assert args[0] is features
    assert args[1]["recent_load_7d"] == 120
    assert args[1]["fitness_level"] == "beginner"
    assert args[2] == {"note": "recently did intervals"}

    memory.update.assert_called_once_with(
        "user1",
        "sess1",
        features,
        recommendation,
        metadata=activity.metadata.model_dump(mode="json"),
        file_path="x.fit",
    )
    assert result["activity_features"] == features.model_dump()
    assert result["recommendation"] == recommendation.model_dump()
    assert result["user_profile_summary"]["fitness_level"] == "beginner"
    assert "warning" not in result


def test_coordinator_raises_400_on_parse_error():
    parser = mock.MagicMock()
    parser.run.side_effect = FitParseError("invalid fit")
    coord = CoordinatorAgent(parser, mock.MagicMock(), mock.MagicMock(), mock.MagicMock())
    with pytest.raises(CoordinatorError) as excinfo:
        coord.run("x.fit", "u", "s")
    assert excinfo.value.status_code == 400
    assert "invalid fit" in excinfo.value.message


def test_coordinator_raises_500_on_internal_error():
    parser = mock.MagicMock()
    parser.run.side_effect = ValueError("boom")
    coord = CoordinatorAgent(parser, mock.MagicMock(), mock.MagicMock(), mock.MagicMock())
    with pytest.raises(CoordinatorError) as excinfo:
        coord.run("x.fit", "u", "s")
    assert excinfo.value.status_code == 500


def test_coordinator_degrades_when_recommendation_fails():
    activity = make_activity()
    features = make_features()
    parser = mock.MagicMock()
    parser.run.return_value = activity
    feature_agent = mock.MagicMock()
    feature_agent.run.return_value = features
    memory = mock.MagicMock()
    memory.get_context.return_value = {"user_profile": {}, "recent_load_7d": 0, "short_term_context": {}}
    rec_agent = mock.MagicMock()
    rec_agent.run.side_effect = Exception("llm down")

    coord = CoordinatorAgent(parser, feature_agent, memory, rec_agent)
    result = coord.run("x.fit", "u", "s")

    assert result["recommendation"] is None
    assert "warning" in result
    assert "llm down" in result["warning"]
    # memory.update must not be called when recommendation is None
    memory.update.assert_not_called()


def test_coordinator_continues_when_memory_fails():
    activity = make_activity()
    features = make_features()
    recommendation = make_recommendation()
    parser = mock.MagicMock()
    parser.run.return_value = activity
    feature_agent = mock.MagicMock()
    feature_agent.run.return_value = features
    memory = mock.MagicMock()
    memory.get_context.return_value = {"user_profile": {}, "recent_load_7d": 0, "short_term_context": {}}
    memory.update.side_effect = Exception("db down")
    rec_agent = mock.MagicMock()
    rec_agent.run.return_value = recommendation

    coord = CoordinatorAgent(parser, feature_agent, memory, rec_agent)
    result = coord.run("x.fit", "u", "s")
    assert result["recommendation"] == recommendation.model_dump()

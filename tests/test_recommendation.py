from types import SimpleNamespace
from unittest import mock

import pytest

from app.agents.recommendation_agent import RecommendationAgent
from app.models.features import ActivityFeatures
from app.services.recommendation_rules import apply_rules


def make_features(
    training_load=100.0,
    intensity_distribution="endurance",
    hr_zones=None,
    **kwargs,
):
    defaults = dict(
        total_duration_seconds=3600.0,
        total_distance_m=10000.0,
        avg_hr=140.0,
        max_hr=180,
        hr_zones=hr_zones
        or {"zone1": 80.0, "zone2": 20.0, "zone3": 0.0, "zone4": 0.0, "zone5": 0.0},
        avg_pace_min_per_km=6.0,
        elevation_gain_m=100.0,
        training_load=training_load,
        interval_training=False,
        intensity_distribution=intensity_distribution,
    )
    defaults.update(kwargs)
    return ActivityFeatures(**defaults)


def test_rules_low_load_recovery_days_1():
    features = make_features(training_load=100.0)
    rules = apply_rules(features, {"fitness_level": "beginner"})
    assert rules["recovery_days"] == 1


def test_rules_high_load_recovery_days_2():
    features = make_features(training_load=200.0)
    rules = apply_rules(features, {})
    assert rules["recovery_days"] == 2
    assert rules["training_zones"]["hr_zone"] == "Z1-Z2"


def test_rules_very_high_load_recovery_days_3():
    features = make_features(training_load=300.0)
    rules = apply_rules(features, {})
    assert rules["recovery_days"] == 3


def test_rules_z45_ratio_triggers_recovery():
    zones = {"zone1": 0.0, "zone2": 10.0, "zone3": 20.0, "zone4": 30.0, "zone5": 40.0}
    features = make_features(training_load=100.0, hr_zones=zones)
    rules = apply_rules(features, {})
    assert rules["recovery_days"] == 3  # Z4+Z5 = 70% > 50%


def test_rules_injury_adds_day_and_clamps():
    features = make_features(training_load=300.0)
    rules = apply_rules(features, {"injury_history": "left knee injury"})
    assert rules["recovery_days"] == 4

    # clamp at 7 even with injury on top of very high load
    features = make_features(training_load=100.0, hr_zones={
        "zone1": 0.0, "zone2": 0.0, "zone3": 0.0, "zone4": 0.0, "zone5": 100.0,
    })
    rules = apply_rules(features, {"injury_history": "injury"})
    assert rules["recovery_days"] <= 7


def test_rules_next_intensity_by_distribution():
    # endurance -> tempo
    features = make_features(training_load=100.0, intensity_distribution="endurance")
    rules = apply_rules(features, {"fitness_level": "beginner"})
    assert rules["training_zones"]["hr_zone"] == "Z3"
    assert "节奏跑" in rules["rule_based_suggestion"]

    # interval -> endurance recovery
    features = make_features(training_load=100.0, intensity_distribution="interval")
    rules = apply_rules(features, {})
    assert rules["training_zones"]["hr_zone"] == "Z2-Z3"


def test_recommendation_agent_rules_only_when_llm_disabled():
    features = make_features(training_load=100.0)
    rules = apply_rules(features, {"fitness_level": "beginner"})
    agent = RecommendationAgent(llm_enabled=False)
    rec = agent.run(features, {"fitness_level": "beginner"}, {})
    assert rec.suggestion_text == rules["rule_based_suggestion"]
    assert rec.recovery_days == rules["recovery_days"]
    assert rec.training_zones == rules["training_zones"]


def test_recommendation_agent_falls_back_without_api_key():
    features = make_features(training_load=100.0)
    rules = apply_rules(features, {})
    agent = RecommendationAgent(llm_enabled=True, openai_api_key=None)
    rec = agent.run(features, {}, {})
    assert rec.suggestion_text == rules["rule_based_suggestion"]


def test_recommendation_agent_llm_generation():
    features = make_features(training_load=100.0)

    class FakeCompletions:
        def create(self, **kwargs):
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(content='{"suggestion_text": "这是LLM生成的建议"}')
                    )
                ]
            )

    class FakeChat:
        def __init__(self):
            self.completions = FakeCompletions()

    class FakeOpenAI:
        def __init__(self, *args, **kwargs):
            self.chat = FakeChat()

    agent = RecommendationAgent(llm_enabled=True, openai_api_key="sk-test")
    with mock.patch("app.agents.recommendation_agent.OpenAI", FakeOpenAI):
        rec = agent.run(features, {}, {})

    assert rec.suggestion_text == "这是LLM生成的建议"
    assert rec.recovery_days == 1  # rules still control recovery days


def test_recommendation_agent_llm_invalid_output_falls_back():
    features = make_features(training_load=100.0)
    rules = apply_rules(features, {})

    class FakeCompletions:
        def create(self, **kwargs):
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content="not valid json"))]
            )

    class FakeChat:
        def __init__(self):
            self.completions = FakeCompletions()

    class FakeOpenAI:
        def __init__(self, *args, **kwargs):
            self.chat = FakeChat()

    agent = RecommendationAgent(llm_enabled=True, openai_api_key="sk-test")
    with mock.patch("app.agents.recommendation_agent.OpenAI", FakeOpenAI):
        rec = agent.run(features, {}, {})

    assert rec.suggestion_text == rules["rule_based_suggestion"]

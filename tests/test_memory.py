import json
import time
from datetime import datetime, timedelta

from app.agents.memory_agent import MemoryAgent
from app.db import database
from app.models.features import ActivityFeatures
from app.models.recommendation import Recommendation


def make_features(training_load=180.0):
    return ActivityFeatures(
        total_duration_seconds=3600.0,
        total_distance_m=10000.0,
        avg_hr=150.0,
        max_hr=180,
        hr_zones={"zone1": 0.0, "zone2": 50.0, "zone3": 50.0, "zone4": 0.0, "zone5": 0.0},
        avg_pace_min_per_km=6.0,
        elevation_gain_m=100.0,
        training_load=training_load,
        interval_training=False,
        intensity_distribution="tempo",
    )


def make_recommendation():
    return Recommendation(
        suggestion_text="建议进行轻松跑恢复",
        recovery_days=1,
        training_zones={"hr_zone": "Z2", "pace_range": "6:00-6:30 min/km"},
    )


def test_get_context_unknown_user(tmp_path):
    agent = MemoryAgent(db_path=str(tmp_path / "m.db"))
    ctx = agent.get_context("nobody", "sess")
    assert ctx["user_profile"] == {}
    assert ctx["recent_load_7d"] == 0.0
    assert ctx["short_term_context"] == {}


def test_update_persists_and_updates_context(tmp_path):
    db = str(tmp_path / "m.db")
    agent = MemoryAgent(db_path=db)
    features = make_features()
    rec = make_recommendation()

    agent.update("u1", "s1", features, rec)

    # Activity persisted
    rows = database.get_recent_activities("u1", db_path=db)
    assert len(rows) == 1
    assert "training_load" in rows[0]["features_json"]

    # Profile persisted with rolling loads
    profile = database.get_user_profile("u1", db)
    assert profile["avg_load_7d"] == features.training_load
    assert profile["avg_load_42d"] == features.training_load

    # Short-term context now available (cache hit)
    ctx = agent.get_context("u1", "s1")
    assert ctx["recent_load_7d"] == features.training_load
    assert ctx["short_term_context"]["last_features"]["training_load"] == features.training_load
    assert "last_recommendation" in ctx["short_term_context"]


def test_profile_load_42d_includes_older_activity(tmp_path):
    db = str(tmp_path / "m.db")
    agent = MemoryAgent(db_path=db)
    old_date = (datetime.now() - timedelta(days=30)).isoformat()
    database.insert_activity(
        "u1", old_date, json.dumps({"training_load": 100.0}), "{}", "{}", db_path=db
    )

    agent.update("u1", "s", make_features(training_load=180.0), make_recommendation())

    profile = database.get_user_profile("u1", db)
    # 30-day-old activity counts toward 42d but not 7d
    assert profile["avg_load_7d"] == 180.0
    assert profile["avg_load_42d"] == 280.0


def test_short_term_cache_ttl(tmp_path):
    agent = MemoryAgent(db_path=str(tmp_path / "m.db"), short_term_ttl=0.05)
    agent.short_term_cache["sess"] = {
        "user_profile": {"cached": True},
        "recent_load_7d": 1.0,
        "short_term_context": {},
    }
    # Cache hit while fresh
    ctx = agent.get_context("u", "sess")
    assert ctx["user_profile"].get("cached") is True

    # After expiry the entry is gone -> rebuilt from DB
    time.sleep(0.2)
    ctx = agent.get_context("u", "sess")
    assert "cached" not in ctx["user_profile"]
    assert ctx["recent_load_7d"] == 0.0

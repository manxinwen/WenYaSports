from datetime import datetime, timedelta

import pytest

from app.agents.feature_extractor_agent import FeatureExtractorAgent
from app.models.activity import ActivityMetadata, ActivityRecord, ParsedActivity
from app.services.feature_engine import compute_features


def make_records(hr_fn, n=60, dt=1.0, speed=3.0, start=None):
    start = start or datetime(2026, 1, 1, 8, 0, 0)
    records = []
    for i in range(n):
        t = start + timedelta(seconds=dt * i)
        records.append(
            ActivityRecord(
                timestamp=t,
                hr=hr_fn(i),
                speed=speed,
                alt=10.0 + i * 0.1,
                distance=i * 10.0,
                power=150,
            )
        )
    return records


def make_metadata(records, **kwargs):
    defaults = dict(
        sport="running",
        start_time=records[0].timestamp,
        total_duration_s=59.0,
        total_distance_m=590.0,
        total_ascent_m=100.0,
        total_descent_m=50.0,
        avg_hr=None,
        max_hr=None,
        avg_speed=3.0,
        max_speed=3.5,
    )
    defaults.update(kwargs)
    return ActivityMetadata(**defaults)


def test_compute_features_basic():
    records = make_records(lambda i: 120 + (i % 3), n=60)
    metadata = make_metadata(records, avg_hr=121, max_hr=200)
    feats = compute_features(records, metadata)

    assert feats["total_duration_seconds"] == 59.0
    assert feats["total_distance_m"] == 590.0
    assert feats["training_load"] > 0
    assert feats["elevation_gain_m"] == 100.0
    assert abs(sum(feats["hr_zones"].values()) - 100.0) < 0.5
    assert feats["avg_pace_min_per_km"] is not None
    assert feats["avg_pace_min_per_km"] > 0
    assert feats["interval_training"] in (True, False)
    assert feats["intensity_distribution"] in ("endurance", "tempo", "interval", "mixed")


def test_hr_zones_endurance():
    # Steady low heart rate -> mostly Z1/Z2 -> endurance
    records = make_records(lambda i: 120 + (i % 3), n=60)
    metadata = make_metadata(records, avg_hr=121, max_hr=200)
    feats = compute_features(records, metadata)

    assert feats["hr_zones"]["zone1"] + feats["hr_zones"]["zone2"] > 70
    assert feats["intensity_distribution"] == "endurance"
    assert feats["interval_training"] is False


def test_hr_zones_interval():
    # High fluctuating heart rate -> Z4/Z5 heavy -> interval training
    records = make_records(lambda i: 165 if i % 2 == 0 else 198, n=60)
    metadata = make_metadata(records, avg_hr=181, max_hr=200)
    feats = compute_features(records, metadata)

    assert feats["interval_training"] is True
    assert feats["hr_zones"]["zone4"] + feats["hr_zones"]["zone5"] > 20
    assert feats["intensity_distribution"] == "interval"


def test_feature_extractor_agent_returns_model():
    records = make_records(lambda i: 120 + (i % 3), n=30)
    metadata = make_metadata(records, avg_hr=121, max_hr=200)
    activity = ParsedActivity(metadata=metadata, records=records)
    agent = FeatureExtractorAgent()
    feats = agent.run(activity)

    assert feats.total_duration_seconds == 59.0
    assert feats.training_load > 0
    assert isinstance(feats.hr_zones, dict)
    assert "zone1" in feats.hr_zones

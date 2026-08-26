"""Rule-based training recommendation engine."""

from typing import Dict

from app.models.features import ActivityFeatures

MAX_RECOVERY_DAYS = 7
MIN_RECOVERY_DAYS = 0

# Suggested pace ranges (min/km) by next-session intensity and fitness level
_PACE_RANGES = {
    "beginner": {
        "recovery": "6:30-7:00",
        "endurance": "6:00-6:30",
        "tempo": "5:30-6:00",
        "interval": "4:45-5:15",
    },
    "intermediate": {
        "recovery": "6:00-6:30",
        "endurance": "5:30-6:00",
        "tempo": "5:00-5:30",
        "interval": "4:15-4:45",
    },
    "advanced": {
        "recovery": "5:30-6:00",
        "endurance": "5:00-5:30",
        "tempo": "4:30-5:00",
        "interval": "3:45-4:15",
    },
}

_HR_ZONE_BY_INTENSITY = {
    "recovery": "Z1-Z2",
    "endurance": "Z2-Z3",
    "tempo": "Z3",
    "interval": "Z4-Z5",
}

_INTENSITY_LABELS = {
    "recovery": "轻松恢复跑",
    "endurance": "耐力跑",
    "tempo": "节奏跑",
    "interval": "间歇训练",
}


def _z4z5_ratio(features: ActivityFeatures) -> float:
    zones = features.hr_zones or {}
    return float(zones.get("zone4", 0.0)) + float(zones.get("zone5", 0.0))


def _next_intensity(features: ActivityFeatures, recovery_days: int) -> str:
    if recovery_days >= 2:
        return "recovery"
    dist = features.intensity_distribution
    if dist == "endurance":
        return "tempo"
    if dist == "tempo":
        return "interval"
    if dist == "interval":
        return "endurance"
    return "tempo"  # 'mixed' -> keep a moderate default


def apply_rules(features: ActivityFeatures, user_profile: dict) -> dict:
    """Compute recovery days, training zones and a rule-based suggestion."""
    load = float(features.training_load)
    z45 = _z4z5_ratio(features)

    if load > 250 or z45 > 50:
        recovery_days = 3
    elif load > 150 or z45 > 30:
        recovery_days = 2
    else:
        recovery_days = 1

    profile_text = " ".join(str(v) for v in user_profile.values()).lower()
    if "injury" in profile_text:
        recovery_days += 1

    recovery_days = max(MIN_RECOVERY_DAYS, min(recovery_days, MAX_RECOVERY_DAYS))

    intensity = _next_intensity(features, recovery_days)
    fitness_level = str(user_profile.get("fitness_level") or "beginner").lower()
    fitness_level = fitness_level if fitness_level in _PACE_RANGES else "beginner"

    hr_zone = _HR_ZONE_BY_INTENSITY[intensity]
    pace_range = (
        _PACE_RANGES[fitness_level][intensity] + " min/km"
    )
    training_zones = {"hr_zone": hr_zone, "pace_range": pace_range}

    if intensity == "recovery":
        suggestion = (
            f"本次训练负荷较高，建议优先恢复。未来 {recovery_days} 天以 {hr_zone} 强度进行"
            f"轻松恢复跑，配速控制在 {pace_range}，注意睡眠与营养。"
        )
    else:
        suggestion = (
            f"建议下次训练以{_INTENSITY_LABELS[intensity]}为主，心率区间 {hr_zone}，"
            f"配速 {pace_range}。当前建议恢复 {recovery_days} 天后进行。"
        )

    return {
        "recovery_days": recovery_days,
        "training_zones": training_zones,
        "rule_based_suggestion": suggestion,
    }

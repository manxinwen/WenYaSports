"""Feature computation engine for parsed activity data."""

import statistics
from typing import Dict, List, Optional

from app.models.activity import ActivityMetadata, ActivityRecord

# Default HR zone boundaries (bpm) when max_hr is unknown
DEFAULT_ZONE_BOUNDARIES = [130, 150, 165, 180]

# Training load intensity factor by % of max heart rate
INTENSITY_FACTORS = [
    (50, 1),
    (60, 2),
    (70, 3),
    (80, 4),
    (90, 5),
    (101, 6),
]

DEFAULT_MAX_HR = 180
DEFAULT_INTENSITY_FACTOR = 2.5


def _hr_values(records: List[ActivityRecord]) -> List[int]:
    return [r.hr for r in records if r.hr is not None]


def _rolling_std_max(values: List[float], window: int) -> float:
    """Maximum rolling standard deviation over a fixed window of samples."""
    if len(values) < 2 or window < 2:
        return 0.0
    best = 0.0
    for i in range(len(values) - window + 1):
        s = statistics.pstdev(values[i : i + window])
        if s > best:
            best = s
    return best


def _window_size(records: List[ActivityRecord], window_s: float = 10.0) -> int:
    """Approximate the number of samples inside a time window (default 10s)."""
    timestamps = [r.timestamp for r in records if r.hr is not None]
    if len(timestamps) < 2:
        return 1
    intervals = [
        (timestamps[i + 1] - timestamps[i]).total_seconds()
        for i in range(len(timestamps) - 1)
        if (timestamps[i + 1] - timestamps[i]).total_seconds() > 0
    ]
    if not intervals:
        return 1
    median_dt = statistics.median(intervals)
    return max(1, int(round(window_s / median_dt)))


def _compute_hr_zones(records: List[ActivityRecord], max_hr: Optional[int]) -> Dict[str, float]:
    hrs = _hr_values(records)
    zones = {f"zone{i}": 0.0 for i in range(1, 6)}
    if not hrs:
        return zones

    if max_hr:
        boundaries = [0.6 * max_hr, 0.7 * max_hr, 0.8 * max_hr, 0.9 * max_hr]
    else:
        boundaries = DEFAULT_ZONE_BOUNDARIES

    counts = [0] * 5
    for h in hrs:
        for idx, boundary in enumerate(boundaries):
            if h < boundary:
                counts[idx] += 1
                break
        else:
            counts[4] += 1

    total = len(hrs)
    return {f"zone{i + 1}": round(counts[i] / total * 100.0, 2) for i in range(5)}


def _intensity_factor(avg_hr: Optional[float], max_hr: Optional[int]) -> float:
    if avg_hr is None:
        return DEFAULT_INTENSITY_FACTOR
    max_hr_ref = max_hr or DEFAULT_MAX_HR
    pct = avg_hr / max_hr_ref * 100.0
    for threshold, factor in INTENSITY_FACTORS:
        if pct < threshold:
            return factor
    return 6


def _detect_interval_training(records: List[ActivityRecord]) -> bool:
    hrs = _hr_values(records)
    if hrs:
        window = _window_size(records)
        hr_std = _rolling_std_max([float(h) for h in hrs], window)
        return hr_std > 10 and (max(hrs) - min(hrs)) > 30

    speeds = [r.speed for r in records if r.speed is not None]
    if len(speeds) < 2:
        return False
    return statistics.pstdev(speeds) > 2.0


def _classify_intensity(hr_zones: Dict[str, float], interval_training: bool) -> str:
    z1 = hr_zones["zone1"]
    z2 = hr_zones["zone2"]
    z3 = hr_zones["zone3"]
    z4 = hr_zones["zone4"]
    z5 = hr_zones["zone5"]

    if z1 + z2 > 70:
        return "endurance"
    if z3 > 30:
        return "tempo"
    if z4 + z5 > 20 and interval_training:
        return "interval"
    return "mixed"


def compute_features(
    records: List[ActivityRecord], metadata: ActivityMetadata
) -> dict:
    """Compute training features from parsed activity data."""
    total_duration_s = float(metadata.total_duration_s)
    total_distance_m = float(metadata.total_distance_m)

    hrs = _hr_values(records)
    avg_hr = float(metadata.avg_hr) if metadata.avg_hr is not None else None
    max_hr = int(metadata.max_hr) if metadata.max_hr is not None else None
    if avg_hr is None and hrs:
        avg_hr = float(sum(hrs) / len(hrs))
    if max_hr is None and hrs:
        max_hr = int(max(hrs))

    hr_zones = _compute_hr_zones(records, max_hr)

    if total_distance_m > 0:
        avg_pace_min_per_km = (total_duration_s / 60.0) / (total_distance_m / 1000.0)
    else:
        avg_pace_min_per_km = None

    training_load = (total_duration_s / 60.0) * _intensity_factor(avg_hr, max_hr)

    interval_training = _detect_interval_training(records)
    intensity_distribution = _classify_intensity(hr_zones, interval_training)

    return {
        "total_duration_seconds": total_duration_s,
        "total_distance_m": total_distance_m,
        "avg_hr": round(avg_hr, 2) if avg_hr is not None else None,
        "max_hr": max_hr,
        "hr_zones": hr_zones,
        "avg_pace_min_per_km": round(avg_pace_min_per_km, 2) if avg_pace_min_per_km is not None else None,
        "elevation_gain_m": float(metadata.total_ascent_m),
        "training_load": round(training_load, 2),
        "interval_training": interval_training,
        "intensity_distribution": intensity_distribution,
    }

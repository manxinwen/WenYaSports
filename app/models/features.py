"""Pydantic model for computed activity features."""

from typing import Dict, Optional

from pydantic import BaseModel


class ActivityFeatures(BaseModel):
    total_duration_seconds: float
    total_distance_m: float
    avg_hr: Optional[float] = None
    max_hr: Optional[int] = None
    hr_zones: Dict[str, float]
    avg_pace_min_per_km: Optional[float] = None
    elevation_gain_m: float
    training_load: float
    interval_training: bool
    intensity_distribution: str

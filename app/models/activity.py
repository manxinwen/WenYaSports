"""Pydantic models for parsed activity data."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class ActivityRecord(BaseModel):
    timestamp: datetime
    lat: Optional[float] = None
    lon: Optional[float] = None
    hr: Optional[int] = None
    speed: Optional[float] = None
    alt: Optional[float] = None
    distance: Optional[float] = None
    power: Optional[float] = None


class ActivityMetadata(BaseModel):
    sport: str
    start_time: datetime
    total_duration_s: float
    total_distance_m: float
    total_ascent_m: float
    total_descent_m: float
    avg_hr: Optional[float] = None
    max_hr: Optional[int] = None
    avg_speed: Optional[float] = None
    max_speed: Optional[float] = None


class ParsedActivity(BaseModel):
    metadata: ActivityMetadata
    records: List[ActivityRecord]

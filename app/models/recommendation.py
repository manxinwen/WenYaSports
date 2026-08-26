"""Recommendation models."""

from pydantic import BaseModel


class Recommendation(BaseModel):
    suggestion_text: str
    recovery_days: int
    training_zones: dict  # e.g. {"hr_zone": "Z2", "pace_range": "5:30-6:00 min/km"}


class LLMRecommendationOutput(BaseModel):
    suggestion_text: str

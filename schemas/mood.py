from pydantic import BaseModel, field_validator
from typing import Optional
from datetime import datetime


class MoodLogRequest(BaseModel):
    score: int
    energy_level: Optional[int] = None
    emotions: list[str] = []
    factors: list[str] = []
    notes: Optional[str] = None

    @field_validator("score", "energy_level")
    @classmethod
    def check_range(cls, v):
        if v is not None and not (1 <= v <= 10):
            raise ValueError("Score must be between 1 and 10")
        return v


class MoodEntryOut(BaseModel):
    id: str
    score: int
    energy_level: Optional[int]
    emotions: list[str]
    factors: list[str]
    notes: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class MoodUpdateRequest(BaseModel):
    score: Optional[int] = None
    energy_level: Optional[int] = None
    emotions: Optional[list[str]] = None
    factors: Optional[list[str]] = None
    notes: Optional[str] = None

    @field_validator("score", "energy_level", mode="before")
    @classmethod
    def check_range(cls, v):
        if v is not None and not (1 <= v <= 10):
            raise ValueError("Score must be between 1 and 10")
        return v


class MoodAnalyticsOut(BaseModel):
    total_entries: int
    avg_score: float
    avg_energy: Optional[float]
    trend: str                    # "rising" | "falling" | "stable" | "insufficient_data"
    weekly_avgs: list[float]
    emotion_freq: dict[str, int]
    factor_freq: dict[str, int]
    top_positive_factors: list[str]
    top_negative_factors: list[str]
    insights: list[str]

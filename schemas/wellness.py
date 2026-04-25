from pydantic import BaseModel, field_validator
from typing import Optional
from datetime import datetime


class Goal(BaseModel):
    title: str
    target: str
    unit: str = ""
    current: str = "0"
    deadline: Optional[str] = None


class Activity(BaseModel):
    name: str
    frequency: str          # "daily" | "3x/week" | "weekly"
    duration_min: int = 10
    category: str = "general"  # "mindfulness" | "physical" | "social" | "sleep"


class WellnessPlanCreateRequest(BaseModel):
    title: str
    description: Optional[str] = None
    goals: list[Goal] = []
    activities: list[Activity] = []
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class WellnessPlanUpdateRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    goals: Optional[list[Goal]] = None
    activities: Optional[list[Activity]] = None
    status: Optional[str] = None
    progress_pct: Optional[float] = None


class WellnessPlanOut(BaseModel):
    id: str
    title: str
    description: Optional[str]
    goals: list[dict]
    activities: list[dict]
    start_date: Optional[str]
    end_date: Optional[str]
    status: str
    ai_generated: bool
    progress_pct: float
    created_at: datetime

    model_config = {"from_attributes": True}


class GeneratePlanRequest(BaseModel):
    focus: Optional[str] = None   # user's free-text goal/focus


# ── Plan Tasks ────────────────────────────────────────────────────────────────

class PlanTaskCreateRequest(BaseModel):
    title: str
    notes: Optional[str] = None
    sort_order: int = 0

    @field_validator("title")
    @classmethod
    def title_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Title cannot be empty")
        return v.strip()


class PlanTaskUpdateRequest(BaseModel):
    title: Optional[str] = None
    notes: Optional[str] = None
    completed: Optional[bool] = None
    time_logged_min: Optional[int] = None

    @field_validator("time_logged_min")
    @classmethod
    def time_non_negative(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v < 0:
            raise ValueError("time_logged_min must be >= 0")
        return v


class PlanTaskOut(BaseModel):
    id: str
    plan_id: str
    title: str
    notes: Optional[str]
    completed: bool
    time_logged_min: int
    sort_order: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

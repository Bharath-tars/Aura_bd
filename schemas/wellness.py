from pydantic import BaseModel
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

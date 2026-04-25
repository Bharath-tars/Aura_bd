from pydantic import BaseModel
from typing import Optional


class DashboardOut(BaseModel):
    wellness_score: float           # 0-100 composite
    current_streak: int
    longest_streak: int
    mood_avg_7d: Optional[float]
    mood_avg_30d: Optional[float]
    mood_trend: str                 # "rising" | "falling" | "stable"
    total_journal_entries: int
    active_plans: int
    top_insights: list[str]
    positive_levers: list[dict]     # [{factor, delta}]


class WeeklyReportOut(BaseModel):
    week_label: str
    mood_avg: Optional[float]
    mood_change_pct: Optional[float]
    top_emotions: list[str]
    top_themes: list[str]
    journal_entries: int
    highlights: list[str]
    recommendations: list[str]
    ai_narrative: str

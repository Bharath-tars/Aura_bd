from pydantic import BaseModel
from typing import Optional


class JournalStatsOut(BaseModel):
    total_entries: int
    analyzed_entries: int
    avg_sentiment: Optional[float]


class TaskStatsOut(BaseModel):
    total_tasks: int
    completed_tasks: int
    completion_rate: float
    total_time_logged_min: int


class WellnessStatsOut(BaseModel):
    active_plans: int
    completed_plans: int
    avg_progress_pct: float


class DashboardOut(BaseModel):
    wellness_score: float
    current_streak: int
    longest_streak: int
    # Legacy mood fields (used by Dashboard page)
    mood_avg_7d: Optional[float]
    mood_avg_30d: Optional[float]
    mood_trend: str
    total_journal_entries: int
    active_plans: int
    top_insights: list[str]
    positive_levers: list[dict]
    # Full mood analytics (used by MoodAnalytics page)
    avg_score: float
    trend: str
    total_entries: int
    weekly_avgs: list[float]
    emotion_freq: dict[str, int]
    top_positive_factors: list[str]
    top_negative_factors: list[str]
    # Cross-platform
    journal_stats: JournalStatsOut
    task_stats: TaskStatsOut
    wellness_stats: WellnessStatsOut


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

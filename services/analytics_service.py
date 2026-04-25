from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from models.mood import MoodEntry
from models.journal import JournalEntry
from models.wellness import WellnessPlan
from models.streak import StreakTracking
from services.mood_service import compute_analytics


async def get_dashboard(db: AsyncSession, user_id: str) -> dict:
    mood_analytics = await compute_analytics(db, user_id)

    total_journals = await db.scalar(
        select(func.count()).select_from(JournalEntry).where(JournalEntry.user_id == user_id)
    ) or 0

    active_plans = await db.scalar(
        select(func.count()).select_from(WellnessPlan)
        .where(WellnessPlan.user_id == user_id, WellnessPlan.status == "active")
    ) or 0

    streak = await db.scalar(select(StreakTracking).where(StreakTracking.user_id == user_id))
    current_streak = streak.current_streak if streak else 0
    longest_streak = streak.longest_streak if streak else 0

    # Composite wellness score (0-100)
    mood_component = (mood_analytics["avg_score"] / 10) * 40 if mood_analytics["avg_score"] else 0
    streak_component = min(current_streak / 30, 1.0) * 30
    journal_component = min(total_journals / 20, 1.0) * 15
    plan_component = min(active_plans / 2, 1.0) * 15
    wellness_score = round(mood_component + streak_component + journal_component + plan_component, 1)

    positive_levers = []
    for f in mood_analytics.get("top_positive_factors", []):
        positive_levers.append({"factor": f, "delta": "+?"})

    return {
        "wellness_score": wellness_score,
        "current_streak": current_streak,
        "longest_streak": longest_streak,
        "mood_avg_7d": mood_analytics.get("avg_score"),
        "mood_avg_30d": mood_analytics.get("avg_score"),
        "mood_trend": mood_analytics.get("trend", "insufficient_data"),
        "total_journal_entries": total_journals,
        "active_plans": active_plans,
        "top_insights": mood_analytics.get("insights", []),
        "positive_levers": positive_levers,
    }

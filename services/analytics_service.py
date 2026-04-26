from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from models.mood import MoodEntry
from models.journal import JournalEntry
from models.wellness import WellnessPlan
from models.plan_task import PlanTask
from models.streak import StreakTracking
from services.mood_service import compute_analytics


async def get_dashboard(db: AsyncSession, user_id: str) -> dict:
    mood_analytics = await compute_analytics(db, user_id)

    # Journal stats
    total_journals = await db.scalar(
        select(func.count()).select_from(JournalEntry).where(JournalEntry.user_id == user_id)
    ) or 0
    analyzed_journals = await db.scalar(
        select(func.count()).select_from(JournalEntry)
        .where(JournalEntry.user_id == user_id, JournalEntry.analyzed == True)  # noqa: E712
    ) or 0
    avg_sentiment_row = await db.scalar(
        select(func.avg(JournalEntry.sentiment_score)).where(
            JournalEntry.user_id == user_id, JournalEntry.sentiment_score.isnot(None)
        )
    )

    # Task stats
    total_tasks = await db.scalar(
        select(func.count()).select_from(PlanTask).where(PlanTask.user_id == user_id)
    ) or 0
    completed_tasks = await db.scalar(
        select(func.count()).select_from(PlanTask)
        .where(PlanTask.user_id == user_id, PlanTask.completed == True)  # noqa: E712
    ) or 0
    total_time_min = await db.scalar(
        select(func.sum(PlanTask.time_logged_min)).where(PlanTask.user_id == user_id)
    ) or 0

    # Wellness stats
    active_plans = await db.scalar(
        select(func.count()).select_from(WellnessPlan)
        .where(WellnessPlan.user_id == user_id, WellnessPlan.status == "active")
    ) or 0
    completed_plans = await db.scalar(
        select(func.count()).select_from(WellnessPlan)
        .where(WellnessPlan.user_id == user_id, WellnessPlan.status == "completed")
    ) or 0
    avg_progress_row = await db.scalar(
        select(func.avg(WellnessPlan.progress_pct)).where(
            WellnessPlan.user_id == user_id, WellnessPlan.status == "active"
        )
    )

    streak = await db.scalar(select(StreakTracking).where(StreakTracking.user_id == user_id))
    current_streak = streak.current_streak if streak else 0
    longest_streak = streak.longest_streak if streak else 0

    # Composite wellness score (0-100)
    mood_component = (mood_analytics["avg_score"] / 10) * 40 if mood_analytics["avg_score"] else 0
    streak_component = min(current_streak / 30, 1.0) * 30
    journal_component = min(total_journals / 20, 1.0) * 15
    plan_component = min(active_plans / 2, 1.0) * 15
    wellness_score = round(mood_component + streak_component + journal_component + plan_component, 1)

    # Build positive levers with real numeric delta (fix "+?" bug)
    factor_impact: dict[str, list[float]] = {}
    avg_mood = mood_analytics.get("avg_score", 0) or 0
    # We recompute from mood entries to get the per-factor deltas
    result = await db.execute(
        select(MoodEntry).where(MoodEntry.user_id == user_id)
    )
    entries = result.scalars().all()
    for e in entries:
        for f in (e.factors or []):
            factor_impact.setdefault(f, []).append(e.score)

    positive_levers = []
    for f in mood_analytics.get("top_positive_factors", []):
        if f in factor_impact:
            delta = round(sum(factor_impact[f]) / len(factor_impact[f]) - avg_mood, 2)
        else:
            delta = 0.0
        positive_levers.append({"factor": f, "delta": delta})

    return {
        "wellness_score": wellness_score,
        "current_streak": current_streak,
        "longest_streak": longest_streak,
        # Mood analytics (flattened for dashboard)
        "avg_score": mood_analytics.get("avg_score", 0.0),
        "mood_avg_7d": mood_analytics.get("avg_score"),
        "mood_avg_30d": mood_analytics.get("avg_score"),
        "trend": mood_analytics.get("trend", "insufficient_data"),
        "mood_trend": mood_analytics.get("trend", "insufficient_data"),
        "total_entries": mood_analytics.get("total_entries", 0),
        "weekly_avgs": mood_analytics.get("weekly_avgs", []),
        "emotion_freq": mood_analytics.get("emotion_freq", {}),
        "top_positive_factors": mood_analytics.get("top_positive_factors", []),
        "top_negative_factors": mood_analytics.get("top_negative_factors", []),
        "top_insights": mood_analytics.get("insights", []),
        "positive_levers": positive_levers,
        # Cross-platform stats
        "total_journal_entries": total_journals,
        "journal_stats": {
            "total_entries": total_journals,
            "analyzed_entries": analyzed_journals,
            "avg_sentiment": round(float(avg_sentiment_row), 2) if avg_sentiment_row is not None else None,
        },
        "task_stats": {
            "total_tasks": total_tasks,
            "completed_tasks": completed_tasks,
            "completion_rate": round(completed_tasks / total_tasks * 100, 1) if total_tasks > 0 else 0.0,
            "total_time_logged_min": int(total_time_min),
        },
        "wellness_stats": {
            "active_plans": active_plans,
            "completed_plans": completed_plans,
            "avg_progress_pct": round(float(avg_progress_row), 1) if avg_progress_row is not None else 0.0,
        },
        "active_plans": active_plans,
    }

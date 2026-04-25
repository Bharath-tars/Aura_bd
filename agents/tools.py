"""
LangChain @tool definitions — all DB accessors used by agent nodes.
Each tool is a regular async function registered with @tool decorator.
"""
from langchain_core.tools import tool
from typing import Optional


@tool
async def get_mood_history(user_id: str, days: int = 14) -> dict:
    """Fetch the user's mood entries for the last N days with stats."""
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from sqlalchemy import select
    from datetime import datetime, timedelta, timezone
    from models.mood import MoodEntry
    from config import get_settings
    from services.mood_service import compute_analytics

    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    Session = async_sessionmaker(engine)
    async with Session() as db:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        result = await db.execute(
            select(MoodEntry)
            .where(MoodEntry.user_id == user_id, MoodEntry.created_at >= cutoff)
            .order_by(MoodEntry.created_at)
        )
        entries = result.scalars().all()
        analytics = await compute_analytics(db, user_id)
    await engine.dispose()

    return {
        "entries": [{"score": e.score, "emotions": e.emotions, "factors": e.factors, "created_at": e.created_at.isoformat()} for e in entries],
        "avg_score": analytics["avg_score"],
        "trend": analytics["trend"],
        "weekly_avgs": analytics["weekly_avgs"],
        "top_positive_factors": analytics["top_positive_factors"],
        "top_negative_factors": analytics["top_negative_factors"],
        "insights": analytics["insights"],
    }


@tool
async def get_journal_summary(user_id: str, limit: int = 5) -> dict:
    """Fetch recent journal entries with themes and sentiment (not full content)."""
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from sqlalchemy import select, desc
    from models.journal import JournalEntry
    from config import get_settings

    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    Session = async_sessionmaker(engine)
    async with Session() as db:
        result = await db.execute(
            select(JournalEntry).where(JournalEntry.user_id == user_id)
            .order_by(desc(JournalEntry.created_at)).limit(limit)
        )
        entries = result.scalars().all()
    await engine.dispose()

    all_themes: list[str] = []
    sentiments: list[float] = []
    for e in entries:
        all_themes.extend(e.themes or [])
        if e.sentiment_score is not None:
            sentiments.append(e.sentiment_score)

    from collections import Counter
    top_themes = [t for t, _ in Counter(all_themes).most_common(8)]
    avg_sentiment = sum(sentiments) / len(sentiments) if sentiments else None

    return {
        "recent_entries": [
            {"title": e.title, "themes": e.themes, "sentiment": e.sentiment_score, "date": e.created_at.isoformat()}
            for e in entries
        ],
        "top_themes": top_themes,
        "avg_sentiment": avg_sentiment,
        "sentiment_label": ("positive" if avg_sentiment and avg_sentiment > 0.3
                            else "difficult" if avg_sentiment and avg_sentiment < -0.3
                            else "neutral") if avg_sentiment is not None else "unknown",
    }


@tool
async def get_wellness_context(user_id: str) -> dict:
    """Fetch active wellness plans and goals."""
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from sqlalchemy import select
    from models.wellness import WellnessPlan
    from config import get_settings

    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    Session = async_sessionmaker(engine)
    async with Session() as db:
        result = await db.execute(
            select(WellnessPlan).where(WellnessPlan.user_id == user_id, WellnessPlan.status == "active")
        )
        plans = result.scalars().all()
    await engine.dispose()

    return {
        "active_plans": [{"title": p.title, "goals": p.goals, "activities": p.activities, "progress_pct": p.progress_pct} for p in plans],
        "plan_count": len(plans),
    }


@tool
async def get_graph_insights(user_id: str) -> dict:
    """Get semantic graph derived insights: factor impacts, top themes, emotion correlations."""
    from graph_engine.semantic_graph import rebuild_graph
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from config import get_settings

    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    Session = async_sessionmaker(engine)
    async with Session() as db:
        graph = await rebuild_graph(db)
    await engine.dispose()

    return {
        "positive_levers": graph.find_positive_levers(5),
        "top_themes": graph.get_top_themes(5),
        "emotion_freq": graph.get_emotion_freq(),
        "mood_trend": graph.get_mood_trend(),
    }


@tool
def get_crisis_resources(level: int) -> list[str]:
    """Return appropriate crisis support resources for a given crisis level (1-4)."""
    resources = [
        "Crisis Text Line: text HOME to 741741",
        "988 Suicide & Crisis Lifeline: call or text 988 (US)",
        "iCall (India): 9152987821",
        "Samaritans (UK): call 116 123",
        "International Association for Suicide Prevention: https://www.iasp.info/resources/Crisis_Centres/",
    ]
    if level >= 4:
        return resources
    if level >= 3:
        return resources[:3]
    return resources[:2]

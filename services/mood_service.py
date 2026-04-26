from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from datetime import datetime, timedelta, timezone
from collections import Counter
from models.mood import MoodEntry


async def create_mood_entry(db: AsyncSession, user_id: str, score: int,
                            energy_level: int | None, emotions: list[str],
                            factors: list[str], notes: str | None) -> MoodEntry:
    entry = MoodEntry(
        user_id=user_id, score=score, energy_level=energy_level,
        emotions=emotions, factors=factors, notes=notes,
    )
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    return entry


async def list_mood_entries(db: AsyncSession, user_id: str,
                            skip: int = 0, limit: int = 20) -> tuple[list[MoodEntry], int]:
    total = await db.scalar(
        select(func.count()).select_from(MoodEntry).where(MoodEntry.user_id == user_id)
    )
    result = await db.execute(
        select(MoodEntry).where(MoodEntry.user_id == user_id)
        .order_by(desc(MoodEntry.created_at)).offset(skip).limit(limit)
    )
    return result.scalars().all(), total or 0


async def update_mood_entry(db: AsyncSession, entry: MoodEntry, updates: dict) -> MoodEntry:
    for field, value in updates.items():
        if hasattr(entry, field):
            setattr(entry, field, value)
    await db.flush()
    await db.commit()
    await db.refresh(entry)
    return entry


async def get_mood_entry(db: AsyncSession, user_id: str, entry_id: str) -> MoodEntry | None:
    return await db.scalar(
        select(MoodEntry).where(MoodEntry.user_id == user_id, MoodEntry.id == entry_id)
    )


async def compute_analytics(db: AsyncSession, user_id: str) -> dict:
    result = await db.execute(
        select(MoodEntry).where(MoodEntry.user_id == user_id)
        .order_by(MoodEntry.created_at)
    )
    entries = result.scalars().all()

    if not entries:
        return {
            "total_entries": 0, "avg_score": 0.0, "avg_energy": None,
            "trend": "insufficient_data", "weekly_avgs": [],
            "emotion_freq": {}, "factor_freq": {},
            "top_positive_factors": [], "top_negative_factors": [],
            "insights": ["Log at least 5 mood entries to unlock your first insights."],
        }

    scores = [e.score for e in entries]
    energies = [e.energy_level for e in entries if e.energy_level]
    all_emotions: list[str] = []
    all_factors: list[str] = []
    for e in entries:
        all_emotions.extend(e.emotions or [])
        all_factors.extend(e.factors or [])

    # Weekly averages (last 4 weeks)
    now = datetime.now(timezone.utc)
    weekly_avgs: list[float] = []
    for week_offset in range(3, -1, -1):
        start = now - timedelta(weeks=week_offset + 1)
        end = now - timedelta(weeks=week_offset)
        week_scores = [e.score for e in entries
                       if start <= e.created_at.replace(tzinfo=timezone.utc) < end]
        weekly_avgs.append(round(sum(week_scores) / len(week_scores), 1) if week_scores else 0.0)

    # Trend
    if len(weekly_avgs) >= 3 and all(x > 0 for x in weekly_avgs[-2:]):
        delta = weekly_avgs[-1] - weekly_avgs[-3] if weekly_avgs[-3] > 0 else 0
        trend = "rising" if delta > 0.5 else "falling" if delta < -0.5 else "stable"
    else:
        trend = "insufficient_data"

    emotion_freq = dict(Counter(all_emotions).most_common(15))
    factor_freq = dict(Counter(all_factors).most_common(15))

    # Positive vs negative factors (compared to avg score)
    avg = sum(scores) / len(scores)
    factor_impact: dict[str, list[float]] = {}
    for e in entries:
        for f in (e.factors or []):
            factor_impact.setdefault(f, []).append(e.score)

    positive = sorted(
        [(f, sum(v) / len(v) - avg) for f, v in factor_impact.items() if sum(v) / len(v) > avg],
        key=lambda x: -x[1],
    )
    negative = sorted(
        [(f, avg - sum(v) / len(v)) for f, v in factor_impact.items() if sum(v) / len(v) < avg],
        key=lambda x: -x[1],
    )

    insights = []
    if len(entries) >= 5:
        if positive:
            insights.append(f"'{positive[0][0]}' is your strongest mood booster (+{positive[0][1]:.1f} pts above your average).")
        if negative:
            insights.append(f"'{negative[0][0]}' tends to pull your mood down ({negative[0][1]:.1f} pts below average).")
        if trend == "rising":
            insights.append("Your mood has been improving — keep going.")
        elif trend == "falling":
            insights.append("Your mood has been declining over the past weeks. Consider chatting with your coach.")

    return {
        "total_entries": len(entries),
        "avg_score": round(avg, 1),
        "avg_energy": round(sum(energies) / len(energies), 1) if energies else None,
        "trend": trend,
        "weekly_avgs": weekly_avgs,
        "emotion_freq": emotion_freq,
        "factor_freq": factor_freq,
        "top_positive_factors": [f for f, _ in positive[:3]],
        "top_negative_factors": [f for f, _ in negative[:3]],
        "insights": insights,
    }

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import date, timedelta
from ..models.streak import StreakTracking


async def get_or_create_streak(db: AsyncSession, user_id: str) -> StreakTracking:
    streak = await db.scalar(select(StreakTracking).where(StreakTracking.user_id == user_id))
    if not streak:
        streak = StreakTracking(user_id=user_id)
        db.add(streak)
        await db.commit()
        await db.refresh(streak)
    return streak


async def record_checkin(db: AsyncSession, user_id: str) -> StreakTracking:
    streak = await get_or_create_streak(db, user_id)
    today = date.today().isoformat()
    yesterday = (date.today() - timedelta(days=1)).isoformat()

    if streak.last_checkin_date == today:
        return streak  # already checked in today

    if streak.last_checkin_date == yesterday:
        streak.current_streak += 1
    else:
        streak.current_streak = 1  # reset

    if streak.current_streak > streak.longest_streak:
        streak.longest_streak = streak.current_streak

    streak.last_checkin_date = today
    await db.commit()
    await db.refresh(streak)
    return streak

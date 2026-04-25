from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from database import get_db
from models.user import User
from utils.auth import get_current_user
from services.streak_service import get_or_create_streak

router = APIRouter(prefix="/streak", tags=["streak"])


class StreakOut(BaseModel):
    current_streak: int
    longest_streak: int
    last_checkin_date: str | None


@router.get("/", response_model=StreakOut)
async def get_streak(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    streak = await get_or_create_streak(db, current_user.id)
    return StreakOut(
        current_streak=streak.current_streak,
        longest_streak=streak.longest_streak,
        last_checkin_date=streak.last_checkin_date,
    )

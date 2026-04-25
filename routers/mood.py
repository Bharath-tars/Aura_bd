from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from ..database import get_db
from ..models.user import User
from ..utils.auth import get_current_user
from ..schemas.mood import MoodLogRequest, MoodEntryOut, MoodAnalyticsOut
from ..services import mood_service, streak_service

router = APIRouter(prefix="/mood", tags=["mood"])


@router.post("/", response_model=MoodEntryOut, status_code=201)
async def log_mood(
    body: MoodLogRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    entry = await mood_service.create_mood_entry(
        db, current_user.id, body.score, body.energy_level,
        body.emotions, body.factors, body.notes,
    )
    await streak_service.record_checkin(db, current_user.id)
    return MoodEntryOut.model_validate(entry)


@router.get("/analytics", response_model=MoodAnalyticsOut)
async def mood_analytics(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    data = await mood_service.compute_analytics(db, current_user.id)
    return MoodAnalyticsOut(**data)


@router.get("/", response_model=dict)
async def list_moods(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    entries, total = await mood_service.list_mood_entries(db, current_user.id, skip, limit)
    return {
        "data": [MoodEntryOut.model_validate(e) for e in entries],
        "total": total, "skip": skip, "limit": limit,
        "has_more": (skip + limit) < total,
        "message": "ok",
    }


@router.get("/{entry_id}", response_model=MoodEntryOut)
async def get_mood(
    entry_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    entry = await mood_service.get_mood_entry(db, current_user.id, entry_id)
    if not entry:
        raise HTTPException(404, "Mood entry not found")
    return MoodEntryOut.model_validate(entry)


@router.delete("/{entry_id}", status_code=204)
async def delete_mood(
    entry_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    entry = await mood_service.get_mood_entry(db, current_user.id, entry_id)
    if not entry:
        raise HTTPException(404, "Mood entry not found")
    await db.delete(entry)
    await db.commit()

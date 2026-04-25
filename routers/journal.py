from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db
from models.user import User
from utils.auth import get_current_user
from schemas.journal import (
    JournalCreateRequest, JournalUpdateRequest,
    JournalEntryOut, JournalListItem,
)
from services import journal_service

router = APIRouter(prefix="/journal", tags=["journal"])


@router.post("/", response_model=JournalEntryOut, status_code=201)
async def create_entry(
    body: JournalCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    entry = await journal_service.create_journal_entry(
        db, current_user.id, body.title, body.content, body.plan_id,
    )
    return JournalEntryOut.model_validate(entry)


@router.get("/", response_model=dict)
async def list_entries(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    entries, total = await journal_service.list_journal_entries(db, current_user.id, skip, limit)
    return {
        "data": [JournalListItem.model_validate(e) for e in entries],
        "total": total, "skip": skip, "limit": limit,
        "has_more": (skip + limit) < total,
        "message": "ok",
    }


@router.get("/{entry_id}", response_model=JournalEntryOut)
async def get_entry(
    entry_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    entry = await journal_service.get_journal_entry(db, current_user.id, entry_id)
    if not entry:
        raise HTTPException(404, "Journal entry not found")
    return JournalEntryOut.model_validate(entry)


@router.put("/{entry_id}", response_model=JournalEntryOut)
async def update_entry(
    entry_id: str,
    body: JournalUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    entry = await journal_service.get_journal_entry(db, current_user.id, entry_id)
    if not entry:
        raise HTTPException(404, "Journal entry not found")
    updated = await journal_service.update_journal_entry(db, entry, body.title, body.content)
    return JournalEntryOut.model_validate(updated)


@router.delete("/{entry_id}", status_code=204)
async def delete_entry(
    entry_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    entry = await journal_service.get_journal_entry(db, current_user.id, entry_id)
    if not entry:
        raise HTTPException(404, "Journal entry not found")
    await db.delete(entry)
    await db.commit()


@router.post("/{entry_id}/analyze", response_model=JournalEntryOut)
async def analyze_entry(
    entry_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    entry = await journal_service.get_journal_entry(db, current_user.id, entry_id)
    if not entry:
        raise HTTPException(404, "Journal entry not found")

    try:
        from agents.graph import run_journal_analysis
        result = await run_journal_analysis(
            user_id=current_user.id,
            journal_content=entry.content,
            db=db,
        )
        updated = await journal_service.save_ai_insights(
            db, entry,
            insights=result.get("insights", []),
            sentiment=result.get("sentiment_score"),
            themes=result.get("themes", []),
        )
        return JournalEntryOut.model_validate(updated)
    except Exception as e:
        raise HTTPException(500, f"AI analysis failed: {str(e)}")

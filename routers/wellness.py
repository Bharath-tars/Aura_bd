from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from ..database import get_db
from ..models.user import User
from ..utils.auth import get_current_user
from ..schemas.wellness import (
    WellnessPlanCreateRequest, WellnessPlanUpdateRequest,
    WellnessPlanOut, GeneratePlanRequest,
)
from ..services import wellness_service

router = APIRouter(prefix="/wellness", tags=["wellness"])


@router.get("/plans", response_model=dict)
async def list_plans(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    plans = await wellness_service.list_plans(db, current_user.id)
    return {"data": [WellnessPlanOut.model_validate(p) for p in plans], "message": "ok"}


@router.post("/plans", response_model=WellnessPlanOut, status_code=201)
async def create_plan(
    body: WellnessPlanCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    plan = await wellness_service.create_plan(
        db, current_user.id, body.title, body.description,
        body.goals, body.activities, body.start_date, body.end_date,
    )
    return WellnessPlanOut.model_validate(plan)


@router.put("/plans/{plan_id}", response_model=WellnessPlanOut)
async def update_plan(
    plan_id: str,
    body: WellnessPlanUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    plan = await wellness_service.get_plan(db, current_user.id, plan_id)
    if not plan:
        raise HTTPException(404, "Plan not found")
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if "goals" in updates:
        updates["goals"] = [g.model_dump() if hasattr(g, "model_dump") else g for g in updates["goals"]]
    if "activities" in updates:
        updates["activities"] = [a.model_dump() if hasattr(a, "model_dump") else a for a in updates["activities"]]
    updated = await wellness_service.update_plan(db, plan, updates)
    return WellnessPlanOut.model_validate(updated)


@router.delete("/plans/{plan_id}", status_code=204)
async def delete_plan(
    plan_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    plan = await wellness_service.get_plan(db, current_user.id, plan_id)
    if not plan:
        raise HTTPException(404, "Plan not found")
    await db.delete(plan)
    await db.commit()


@router.post("/generate", response_model=WellnessPlanOut, status_code=201)
async def generate_plan(
    body: GeneratePlanRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        from ..agents.graph import run_plan_generation
        result = await run_plan_generation(
            user_id=current_user.id, focus=body.focus, db=db,
        )
        plan = await wellness_service.create_plan(
            db, current_user.id,
            title=result.get("title", "AI Wellness Plan"),
            description=result.get("description"),
            goals=result.get("goals", []),
            activities=result.get("activities", []),
            start_date=result.get("start_date"),
            end_date=result.get("end_date"),
            ai_generated=True,
        )
        return WellnessPlanOut.model_validate(plan)
    except Exception as e:
        raise HTTPException(500, f"Plan generation failed: {str(e)}")

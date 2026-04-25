from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db
from models.user import User
from utils.auth import get_current_user
from schemas.wellness import PlanTaskCreateRequest, PlanTaskUpdateRequest, PlanTaskOut
from services import wellness_service, task_service

router = APIRouter(prefix="/wellness", tags=["tasks"])


@router.get("/plans/{plan_id}/tasks", response_model=list[PlanTaskOut])
async def list_tasks(
    plan_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    plan = await wellness_service.get_plan(db, current_user.id, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    return await task_service.list_tasks(db, current_user.id, plan_id)


@router.post("/plans/{plan_id}/tasks", response_model=PlanTaskOut, status_code=201)
async def create_task(
    plan_id: str,
    body: PlanTaskCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    plan = await wellness_service.get_plan(db, current_user.id, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    return await task_service.create_task(
        db, current_user.id, plan_id, body.title, body.notes, body.sort_order
    )


@router.patch("/plans/{plan_id}/tasks/{task_id}", response_model=PlanTaskOut)
async def update_task(
    plan_id: str,
    task_id: str,
    body: PlanTaskUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    task = await task_service.get_task(db, current_user.id, task_id)
    if not task or task.plan_id != plan_id:
        raise HTTPException(status_code=404, detail="Task not found")
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    return await task_service.update_task(db, task, updates)


@router.delete("/plans/{plan_id}/tasks/{task_id}", status_code=204)
async def delete_task(
    plan_id: str,
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    task = await task_service.get_task(db, current_user.id, task_id)
    if not task or task.plan_id != plan_id:
        raise HTTPException(status_code=404, detail="Task not found")
    await task_service.delete_task(db, task)

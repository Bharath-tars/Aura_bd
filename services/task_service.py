from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from models.plan_task import PlanTask
from models.wellness import WellnessPlan


async def list_tasks(db: AsyncSession, user_id: str, plan_id: str) -> list[PlanTask]:
    result = await db.execute(
        select(PlanTask)
        .where(PlanTask.user_id == user_id, PlanTask.plan_id == plan_id)
        .order_by(PlanTask.sort_order, PlanTask.created_at)
    )
    return list(result.scalars().all())


async def get_task(db: AsyncSession, user_id: str, task_id: str) -> PlanTask | None:
    return await db.scalar(
        select(PlanTask).where(PlanTask.user_id == user_id, PlanTask.id == task_id)
    )


async def create_task(
    db: AsyncSession,
    user_id: str,
    plan_id: str,
    title: str,
    notes: str | None = None,
    sort_order: int = 0,
) -> PlanTask:
    task = PlanTask(
        user_id=user_id,
        plan_id=plan_id,
        title=title,
        notes=notes,
        sort_order=sort_order,
    )
    db.add(task)
    await db.flush()
    await _recalc_progress(db, user_id, plan_id)
    await db.commit()
    await db.refresh(task)
    return task


async def update_task(db: AsyncSession, task: PlanTask, updates: dict) -> PlanTask:
    for field, value in updates.items():
        setattr(task, field, value)
    await db.flush()
    await _recalc_progress(db, task.user_id, task.plan_id)
    await db.commit()
    await db.refresh(task)
    return task


async def delete_task(db: AsyncSession, task: PlanTask) -> None:
    user_id = task.user_id
    plan_id = task.plan_id
    await db.delete(task)
    await db.flush()
    await _recalc_progress(db, user_id, plan_id)
    await db.commit()


async def bulk_create_tasks(
    db: AsyncSession,
    user_id: str,
    plan_id: str,
    tasks: list[dict],
) -> list[PlanTask]:
    objects = [PlanTask(user_id=user_id, plan_id=plan_id, **t) for t in tasks]
    db.add_all(objects)
    await db.flush()
    await _recalc_progress(db, user_id, plan_id)
    await db.commit()
    return objects


async def _recalc_progress(db: AsyncSession, user_id: str, plan_id: str) -> None:
    total = await db.scalar(
        select(func.count()).select_from(PlanTask)
        .where(PlanTask.user_id == user_id, PlanTask.plan_id == plan_id)
    )
    if not total:
        pct = 0.0
    else:
        done = await db.scalar(
            select(func.count()).select_from(PlanTask)
            .where(
                PlanTask.user_id == user_id,
                PlanTask.plan_id == plan_id,
                PlanTask.completed == True,  # noqa: E712
            )
        )
        pct = round(((done or 0) / total) * 100, 1)

    plan = await db.scalar(
        select(WellnessPlan)
        .where(WellnessPlan.user_id == user_id, WellnessPlan.id == plan_id)
    )
    if plan:
        plan.progress_pct = pct

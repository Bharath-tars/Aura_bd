from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from models.wellness import WellnessPlan


def _activity_to_task_title(act: dict) -> str:
    name = act.get("name", "Activity")
    freq = act.get("frequency", "")
    dur = act.get("duration_min", 0)
    parts = [name]
    if freq:
        parts.append(freq)
    if dur:
        parts.append(f"{dur} min")
    return " — ".join(parts)


async def create_plan(db: AsyncSession, user_id: str, title: str,
                      description: str | None, goals: list, activities: list,
                      start_date: str | None, end_date: str | None,
                      ai_generated: bool = False) -> WellnessPlan:
    acts = [a.model_dump() if hasattr(a, "model_dump") else a for a in activities]
    plan = WellnessPlan(
        user_id=user_id, title=title, description=description,
        goals=[g.model_dump() if hasattr(g, "model_dump") else g for g in goals],
        activities=acts,
        start_date=start_date, end_date=end_date, ai_generated=ai_generated,
    )
    db.add(plan)
    await db.commit()
    await db.refresh(plan)

    if acts:
        from services import task_service
        tasks_data = [
            {"title": _activity_to_task_title(act), "sort_order": i}
            for i, act in enumerate(acts)
        ]
        await task_service.bulk_create_tasks(db, user_id, plan.id, tasks_data)
        await db.refresh(plan)

    return plan


async def list_plans(db: AsyncSession, user_id: str) -> list[WellnessPlan]:
    result = await db.execute(
        select(WellnessPlan).where(WellnessPlan.user_id == user_id)
        .order_by(desc(WellnessPlan.created_at))
    )
    return result.scalars().all()


async def get_plan(db: AsyncSession, user_id: str, plan_id: str) -> WellnessPlan | None:
    return await db.scalar(
        select(WellnessPlan).where(WellnessPlan.user_id == user_id, WellnessPlan.id == plan_id)
    )


async def update_plan(db: AsyncSession, plan: WellnessPlan, updates: dict) -> WellnessPlan:
    for field, value in updates.items():
        if value is not None:
            setattr(plan, field, value)
    await db.commit()
    await db.refresh(plan)
    return plan

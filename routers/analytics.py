from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db
from models.user import User
from utils.auth import get_current_user
from schemas.analytics import DashboardOut
from services.analytics_service import get_dashboard

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/dashboard", response_model=DashboardOut)
async def dashboard(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    data = await get_dashboard(db, current_user.id)
    return DashboardOut(**data)

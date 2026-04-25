from sqlalchemy import String, Float, Date, Boolean, DateTime, ForeignKey, JSON, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
import enum
from uuid import uuid4
from database import Base


class PlanStatus(str, enum.Enum):
    active = "active"
    paused = "paused"
    completed = "completed"


class WellnessPlan(Base):
    __tablename__ = "wellness_plans"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(String(1000), nullable=True)
    goals: Mapped[list] = mapped_column(JSON, default=list)       # [{title,target,unit,current,deadline}]
    activities: Mapped[list] = mapped_column(JSON, default=list)  # [{name,frequency,duration_min,category}]
    start_date: Mapped[str] = mapped_column(String(10), nullable=True)
    end_date: Mapped[str] = mapped_column(String(10), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active")
    ai_generated: Mapped[bool] = mapped_column(Boolean, default=False)
    progress_pct: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="wellness_plans")

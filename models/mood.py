from sqlalchemy import String, Integer, Float, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from uuid import uuid4
from ..database import Base


class MoodEntry(Base):
    __tablename__ = "mood_entries"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False)           # 1-10
    energy_level: Mapped[int] = mapped_column(Integer, nullable=True)     # 1-10
    emotions: Mapped[list] = mapped_column(JSON, default=list)            # ["anxious","content",...]
    factors: Mapped[list] = mapped_column(JSON, default=list)             # ["exercise","poor_sleep",...]
    notes: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="mood_entries")

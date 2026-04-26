from sqlalchemy import String, Boolean, DateTime, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from uuid import uuid4
from database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String, nullable=False)
    timezone: Mapped[str] = mapped_column(String(50), default="UTC")
    notification_time: Mapped[str] = mapped_column(String(10), default="09:00")
    onboarding_complete: Mapped[bool] = mapped_column(Boolean, default=False)
    gender: Mapped[str] = mapped_column(String(20), nullable=True)
    age: Mapped[int] = mapped_column(Integer, nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    mood_entries = relationship("MoodEntry", back_populates="user", cascade="all, delete-orphan")
    journal_entries = relationship("JournalEntry", back_populates="user", cascade="all, delete-orphan")
    wellness_plans = relationship("WellnessPlan", back_populates="user", cascade="all, delete-orphan")
    chat_sessions = relationship("ChatSession", back_populates="user", cascade="all, delete-orphan")
    streak = relationship("StreakTracking", back_populates="user", cascade="all, delete-orphan", uselist=False)

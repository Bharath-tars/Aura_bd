from pydantic import BaseModel, field_validator
from typing import Optional
from datetime import datetime


class JournalCreateRequest(BaseModel):
    title: str
    content: str

    @field_validator("title")
    @classmethod
    def title_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Title cannot be empty")
        return v.strip()

    @field_validator("content")
    @classmethod
    def content_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Content cannot be empty")
        return v


class JournalUpdateRequest(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None


class AIInsight(BaseModel):
    title: str
    body: str
    type: str  # "theme" | "pattern" | "recommendation" | "reflection"


class JournalEntryOut(BaseModel):
    id: str
    title: str
    content: str
    ai_insights: Optional[list[AIInsight]]
    sentiment_score: Optional[float]
    themes: list[str]
    word_count: int
    analyzed: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class JournalListItem(BaseModel):
    id: str
    title: str
    themes: list[str]
    sentiment_score: Optional[float]
    word_count: int
    analyzed: bool
    created_at: datetime

    model_config = {"from_attributes": True}

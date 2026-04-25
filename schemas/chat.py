from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class ChatSessionOut(BaseModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ChatMessageOut(BaseModel):
    id: str
    session_id: str
    role: str
    content: str
    crisis_level: int
    created_at: datetime

    model_config = {"from_attributes": True}


class SendMessageRequest(BaseModel):
    content: str


class CreateSessionRequest(BaseModel):
    title: str = "New conversation"

import json
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db
from models.user import User
from utils.auth import get_current_user
from services import therapist_service
from datetime import datetime
from typing import Optional

router = APIRouter(prefix="/therapist", tags=["therapist"])


class TherapistSessionOut(BaseModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TherapistMessageOut(BaseModel):
    id: str
    session_id: str
    role: str
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}


class SendMessageRequest(BaseModel):
    message: str


class RenameSessionRequest(BaseModel):
    title: str


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------

@router.get("/sessions", response_model=dict)
async def list_sessions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    sessions = await therapist_service.list_sessions(db, current_user.id)
    return {"data": [TherapistSessionOut.model_validate(s) for s in sessions], "message": "ok"}


@router.post("/sessions", response_model=TherapistSessionOut, status_code=201)
async def create_session(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = await therapist_service.create_session(db, current_user.id)
    return TherapistSessionOut.model_validate(session)


@router.patch("/sessions/{session_id}", response_model=TherapistSessionOut)
async def rename_session(
    session_id: str,
    body: RenameSessionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = await therapist_service.get_session(db, current_user.id, session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    updated = await therapist_service.rename_session(db, session, body.title)
    return TherapistSessionOut.model_validate(updated)


@router.delete("/sessions/{session_id}", status_code=204)
async def delete_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = await therapist_service.get_session(db, current_user.id, session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    await therapist_service.delete_session(db, session)


# ---------------------------------------------------------------------------
# Messages
# ---------------------------------------------------------------------------

@router.get("/sessions/{session_id}/messages", response_model=dict)
async def get_messages(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = await therapist_service.get_session(db, current_user.id, session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    messages = await therapist_service.list_messages(db, session_id)
    return {"data": [TherapistMessageOut.model_validate(m) for m in messages], "message": "ok"}


@router.post("/sessions/{session_id}/message")
async def send_message(
    session_id: str,
    body: SendMessageRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = await therapist_service.get_session(db, current_user.id, session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    # Save user message
    await therapist_service.save_message(db, session_id, "user", body.message)

    async def event_stream():
        full_response = ""
        crisis_level = 0

        try:
            from agents.therapist_graph import stream_therapist_response
            async for chunk in stream_therapist_response(
                user_id=current_user.id,
                session_id=session_id,
                message=body.message,
                db=db,
            ):
                if chunk["type"] == "token":
                    full_response += chunk["content"]
                    yield f"data: {json.dumps({'type': 'token', 'content': chunk['content']})}\n\n"
                elif chunk["type"] == "crisis":
                    crisis_level = chunk.get("level", 0)
                    yield f"data: {json.dumps({'type': 'crisis', 'level': crisis_level, 'resources': chunk.get('resources', [])})}\n\n"
        except Exception:
            full_response = "I'm here with you. Take a breath — you're safe to share whatever feels right."
            yield f"data: {json.dumps({'type': 'token', 'content': full_response})}\n\n"

        # Save assistant response
        assistant_msg = await therapist_service.save_message(db, session_id, "assistant", full_response)

        # Auto-name session from first user message
        if session.title == "New session":
            first_words = " ".join(body.message.split()[:6])
            title = first_words[:60] if first_words else "Session"
            await therapist_service.rename_session(db, session, title)

        yield f"data: {json.dumps({'type': 'done', 'message_id': str(assistant_msg.id)})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")

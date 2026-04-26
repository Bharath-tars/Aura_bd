import json
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from database import get_db
from models.user import User
from models.chat import ChatSession, ChatMessage
from utils.auth import get_current_user
from schemas.chat import ChatSessionOut, ChatMessageOut, SendMessageRequest, CreateSessionRequest

router = APIRouter(prefix="/chat", tags=["chat"])


@router.get("/sessions", response_model=dict)
async def list_sessions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ChatSession).where(ChatSession.user_id == current_user.id)
        .order_by(desc(ChatSession.updated_at)).limit(20)
    )
    sessions = result.scalars().all()
    return {"data": [ChatSessionOut.model_validate(s) for s in sessions], "message": "ok"}


@router.post("/sessions", response_model=ChatSessionOut, status_code=201)
async def create_session(
    body: CreateSessionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = ChatSession(user_id=current_user.id, title=body.title)
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return ChatSessionOut.model_validate(session)


@router.get("/sessions/{session_id}/messages", response_model=dict)
async def get_messages(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = await db.scalar(
        select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.user_id == current_user.id,
        )
    )
    if not session:
        raise HTTPException(404, "Session not found")
    result = await db.execute(
        select(ChatMessage).where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at)
    )
    messages = result.scalars().all()
    return {"data": [ChatMessageOut.model_validate(m) for m in messages], "message": "ok"}


@router.post("/sessions/{session_id}/message")
async def send_message(
    session_id: str,
    body: SendMessageRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = await db.scalar(
        select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.user_id == current_user.id,
        )
    )
    if not session:
        raise HTTPException(404, "Session not found")

    # Save user message
    user_msg = ChatMessage(session_id=session_id, role="user", content=body.content)
    db.add(user_msg)
    await db.commit()

    async def event_stream():
        full_response = ""
        crisis_level = 0
        insights = []

        try:
            from agents.graph import stream_wellness_response
            async for chunk in stream_wellness_response(
                user_id=current_user.id,
                session_id=session_id,
                message=body.content,
                db=db,
            ):
                if chunk["type"] == "token":
                    full_response += chunk["content"]
                    yield f"data: {json.dumps({'type': 'token', 'content': chunk['content']})}\n\n"
                elif chunk["type"] == "crisis":
                    crisis_level = chunk.get("level", 0)
                    yield f"data: {json.dumps({'type': 'crisis', 'level': crisis_level, 'resources': chunk.get('resources', [])})}\n\n"
                elif chunk["type"] == "insights":
                    insights = chunk.get("items", [])
                    yield f"data: {json.dumps({'type': 'insights', 'items': insights})}\n\n"
        except Exception as e:
            error_msg = "I'm having trouble connecting right now. Please try again in a moment."
            full_response = error_msg
            yield f"data: {json.dumps({'type': 'token', 'content': error_msg})}\n\n"

        # Save assistant message to DB
        async with db.begin():
            assistant_msg = ChatMessage(
                session_id=session_id,
                role="assistant",
                content=full_response,
                crisis_level=crisis_level,
                metadata_={"insights": insights},
            )
            db.add(assistant_msg)

        # Auto-name session from first user message
        if session.title == "New conversation":
            first_words = " ".join(body.content.split()[:6])
            if first_words:
                session.title = first_words[:60]
                await db.commit()

        yield f"data: {json.dumps({'type': 'done', 'message_id': str(assistant_msg.id)})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.delete("/sessions/{session_id}", status_code=204)
async def delete_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = await db.scalar(
        select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.user_id == current_user.id,
        )
    )
    if not session:
        raise HTTPException(404, "Session not found")
    await db.delete(session)
    await db.commit()

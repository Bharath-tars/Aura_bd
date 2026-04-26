import json
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func
from models.therapist import TherapistSession, TherapistMessage, TherapistMemory

COMPACTION_THRESHOLD = 10


async def list_sessions(db: AsyncSession, user_id: str) -> list[TherapistSession]:
    result = await db.execute(
        select(TherapistSession).where(TherapistSession.user_id == user_id)
        .order_by(desc(TherapistSession.updated_at)).limit(20)
    )
    return result.scalars().all()


async def create_session(db: AsyncSession, user_id: str, title: str = "New session") -> TherapistSession:
    session = TherapistSession(user_id=user_id, title=title)
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


async def get_session(db: AsyncSession, user_id: str, session_id: str) -> TherapistSession | None:
    return await db.scalar(
        select(TherapistSession).where(
            TherapistSession.id == session_id,
            TherapistSession.user_id == user_id,
        )
    )


async def delete_session(db: AsyncSession, session: TherapistSession) -> None:
    await db.delete(session)
    await db.commit()


async def rename_session(db: AsyncSession, session: TherapistSession, title: str) -> TherapistSession:
    session.title = title
    await db.commit()
    await db.refresh(session)
    return session


async def list_messages(db: AsyncSession, session_id: str) -> list[TherapistMessage]:
    result = await db.execute(
        select(TherapistMessage).where(TherapistMessage.session_id == session_id)
        .order_by(TherapistMessage.created_at).limit(100)
    )
    return result.scalars().all()


async def save_message(db: AsyncSession, session_id: str, role: str, content: str) -> TherapistMessage:
    msg = TherapistMessage(session_id=session_id, role=role, content=content)
    db.add(msg)
    # Touch updated_at on the parent session
    session = await db.scalar(select(TherapistSession).where(TherapistSession.id == session_id))
    if session:
        from sqlalchemy import update as sa_update
        await db.execute(
            sa_update(TherapistSession)
            .where(TherapistSession.id == session_id)
            .values(updated_at=func.now())
        )
    await db.commit()
    await db.refresh(msg)
    return msg


async def get_message_count(db: AsyncSession, session_id: str) -> int:
    return await db.scalar(
        select(func.count()).select_from(TherapistMessage)
        .where(TherapistMessage.session_id == session_id)
    ) or 0


async def list_memories(db: AsyncSession, user_id: str, limit: int = 3) -> list[TherapistMemory]:
    result = await db.execute(
        select(TherapistMemory).where(TherapistMemory.user_id == user_id)
        .order_by(desc(TherapistMemory.created_at)).limit(limit)
    )
    return result.scalars().all()


async def compact_memory(db: AsyncSession, user_id: str, session_id: str) -> None:
    """Summarize the oldest COMPACTION_THRESHOLD messages into a TherapistMemory row."""
    from config import get_settings
    settings = get_settings()
    if not settings.gemini_api_key:
        return

    result = await db.execute(
        select(TherapistMessage)
        .where(TherapistMessage.session_id == session_id)
        .order_by(TherapistMessage.created_at)
        .limit(COMPACTION_THRESHOLD)
    )
    msgs = result.scalars().all()
    if len(msgs) < COMPACTION_THRESHOLD:
        return

    transcript = "\n".join(f"{m.role.upper()}: {m.content}" for m in msgs)
    prompt = (
        "Summarize this therapy conversation excerpt into a compact memory record. "
        "Return JSON with keys: summary (string, max 400 words), themes (list of strings), "
        "insights (list of key therapeutic observations, max 5).\n\n"
        f"TRANSCRIPT:\n{transcript}"
    )

    try:
        from google import genai as google_genai
        gclient = google_genai.Client(
            api_key=settings.gemini_api_key,
            http_options={"api_version": "v1"},
        )
        response = gclient.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )
        text = response.text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        data = json.loads(text)

        memory = TherapistMemory(
            user_id=user_id,
            session_id=session_id,
            summary=data.get("summary", transcript[:500]),
            themes=json.dumps(data.get("themes", [])),
            insights=json.dumps(data.get("insights", [])),
            message_count=len(msgs),
        )
        db.add(memory)

        # Delete the summarized messages
        for msg in msgs:
            await db.delete(msg)

        await db.commit()
    except Exception:
        pass  # Compaction failures are non-fatal

"""
Therapist LangGraph — separate pipeline from the wellness coach.

Flow: memory_loader → platform_loader → therapy_response → crisis_detector → memory_compactor → END

Public API:
  stream_therapist_response(user_id, session_id, message, db) → AsyncGenerator
"""
from __future__ import annotations

import json
import logging
import re
from typing import AsyncGenerator, TypedDict

from langgraph.graph import END, StateGraph
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

COMPACTION_THRESHOLD = 10


class TherapistState(TypedDict, total=False):
    user_id: str
    session_id: str
    message: str
    user_profile: dict
    platform_context: dict
    memory_context: list[dict]
    response: str
    crisis_level: int
    crisis_resources: list[str]
    should_compact: bool
    message_count: int


# ---------------------------------------------------------------------------
# Node: memory_loader
# ---------------------------------------------------------------------------

async def memory_loader_node(state: TherapistState) -> dict:
    """Load compacted memory summaries + recent message count."""
    # Lazy imports to avoid circular deps
    from services import therapist_service
    db: AsyncSession = state.get("_db")  # type: ignore[arg-type]
    if not db:
        return {"memory_context": [], "should_compact": False, "message_count": 0}

    memories = await therapist_service.list_memories(db, state["user_id"], limit=3)
    memory_context = [
        {
            "summary": m.summary,
            "themes": json.loads(m.themes or "[]"),
            "insights": json.loads(m.insights or "[]"),
        }
        for m in memories
    ]

    count = await therapist_service.get_message_count(db, state["session_id"])
    should_compact = count >= COMPACTION_THRESHOLD

    return {"memory_context": memory_context, "should_compact": should_compact, "message_count": count}


# ---------------------------------------------------------------------------
# Node: platform_loader
# ---------------------------------------------------------------------------

async def platform_loader_node(state: TherapistState) -> dict:
    """Gather cross-platform context (mood, journals, wellness, user profile)."""
    db: AsyncSession = state.get("_db")  # type: ignore[arg-type]
    if not db:
        return {"platform_context": {}, "user_profile": {}}

    from sqlalchemy import select, desc, func
    from models.user import User
    from models.mood import MoodEntry
    from models.journal import JournalEntry
    from models.wellness import WellnessPlan

    user_id = state["user_id"]

    user = await db.scalar(select(User).where(User.id == user_id))
    profile = {
        "gender": user.gender if user else None,
        "age": user.age if user else None,
        "timezone": user.timezone if user else "UTC",
    }

    # Recent mood average (last 7 entries)
    mood_result = await db.execute(
        select(MoodEntry).where(MoodEntry.user_id == user_id)
        .order_by(desc(MoodEntry.created_at)).limit(7)
    )
    recent_moods = mood_result.scalars().all()
    avg_mood = round(sum(m.score for m in recent_moods) / len(recent_moods), 1) if recent_moods else None

    # Top journal themes
    journal_result = await db.execute(
        select(JournalEntry).where(JournalEntry.user_id == user_id)
        .order_by(desc(JournalEntry.created_at)).limit(5)
    )
    journals = journal_result.scalars().all()
    all_themes: list[str] = []
    for j in journals:
        all_themes.extend(j.themes or [])
    top_themes = list(dict.fromkeys(all_themes))[:5]  # deduplicated, order preserved

    active_plans = await db.scalar(
        select(func.count()).select_from(WellnessPlan)
        .where(WellnessPlan.user_id == user_id, WellnessPlan.status == "active")
    ) or 0

    return {
        "user_profile": profile,
        "platform_context": {
            "avg_mood": avg_mood,
            "journal_themes": top_themes,
            "active_plans": active_plans,
        },
    }


# ---------------------------------------------------------------------------
# Node: therapy_response
# ---------------------------------------------------------------------------

THERAPIST_SYSTEM_TEMPLATE = """\
You are Aura's AI Therapist — a warm, deeply empathetic companion. You hold space for the person to feel heard, understood, and gently supported.

USER PROFILE: {age_gender}
RECENT MOOD AVERAGE: {avg_mood}
RECURRING THEMES FROM THEIR JOURNAL: {themes}
ACTIVE WELLNESS PLANS: {active_plans}
CONVERSATION MEMORY: {memory_summary}

YOUR APPROACH:
- Warm, unhurried, non-judgmental — like a trusted friend who happens to be a therapist
- Use gentle CBT and DBT techniques where natural (thought challenging, grounding, validation)
- Always validate feelings before offering perspective
- Ask one open, curious question at a time — never interrogate
- Reflect feelings back: "It sounds like you're feeling..."
- If anxiety or stress is present, gently offer a grounding exercise
- Never diagnose or pathologize; never give medical advice
- Keep responses conversational length — not too long, not too brief
- Calming, measured tone throughout

PREVIOUS THERAPEUTIC INSIGHTS:
{past_insights}

Remember: you are here to listen, not to fix. Be present."""


async def therapy_response_node(state: TherapistState) -> dict:
    from config import get_settings
    settings = get_settings()
    if not settings.gemini_api_key:
        return {"response": "I'm here for you. Tell me more about what's on your mind."}

    from langchain_google_genai import ChatGoogleGenerativeAI
    from langchain_core.messages import HumanMessage, SystemMessage

    profile = state.get("user_profile", {})
    ctx = state.get("platform_context", {})
    memories = state.get("memory_context", [])

    age = profile.get("age")
    gender = profile.get("gender")
    age_gender = f"{age} years old, {gender}" if age and gender else (
        f"{age} years old" if age else (gender if gender else "profile not set")
    )

    avg_mood = ctx.get("avg_mood")
    avg_mood_str = f"{avg_mood}/10" if avg_mood is not None else "not tracked yet"
    themes = ", ".join(ctx.get("journal_themes", [])) or "no journal entries yet"
    active_plans = ctx.get("active_plans", 0)

    memory_summary = "No previous sessions yet."
    past_insights = "None yet."
    if memories:
        memory_summary = "; ".join(m["summary"][:200] for m in memories[:2])
        all_insights = []
        for m in memories:
            all_insights.extend(m.get("insights", []))
        past_insights = "\n".join(f"- {i}" for i in all_insights[:5]) or "None yet."

    system_prompt = THERAPIST_SYSTEM_TEMPLATE.format(
        age_gender=age_gender,
        avg_mood=avg_mood_str,
        themes=themes,
        active_plans=active_plans,
        memory_summary=memory_summary,
        past_insights=past_insights,
    )

    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key=settings.gemini_api_key,
        temperature=0.65,
    )

    try:
        response = await llm.ainvoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=state["message"]),
        ])
        return {"response": response.content}
    except Exception as e:
        logger.error(f"Therapist response error: {e}")
        return {"response": "I'm here with you. Take a breath — you're safe to share whatever feels right."}


# ---------------------------------------------------------------------------
# Node: crisis_detector (reuses logic from wellness graph)
# ---------------------------------------------------------------------------

async def therapist_crisis_node(state: TherapistState) -> dict:
    from config import get_settings
    settings = get_settings()
    if not settings.gemini_api_key:
        return {"crisis_level": 0, "crisis_resources": []}

    from langchain_google_genai import ChatGoogleGenerativeAI
    from langchain_core.messages import HumanMessage, SystemMessage

    CRISIS_PROMPT = """Assess this message for crisis signals (0=none, 1=mild, 2=moderate, 3=high, 4=critical/self-harm).
Return ONLY JSON: {"level": <int>}"""

    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key=settings.gemini_api_key,
        temperature=0.1,
    )
    try:
        resp = await llm.ainvoke([
            SystemMessage(content=CRISIS_PROMPT),
            HumanMessage(content=state.get("message", "")),
        ])
        match = re.search(r'\{.*\}', resp.content.strip(), re.DOTALL)
        level = int(json.loads(match.group()).get("level", 0)) if match else 0
    except Exception:
        level = 0

    resources: list[str] = []
    if level >= 2:
        from agents.tools import get_crisis_resources
        resources = get_crisis_resources.invoke({"level": level})

    return {"crisis_level": level, "crisis_resources": resources}


# ---------------------------------------------------------------------------
# Node: memory_compactor
# ---------------------------------------------------------------------------

async def memory_compactor_node(state: TherapistState) -> dict:
    if not state.get("should_compact"):
        return {}
    db: AsyncSession = state.get("_db")  # type: ignore[arg-type]
    if not db:
        return {}
    from services import therapist_service
    await therapist_service.compact_memory(db, state["user_id"], state["session_id"])
    return {}


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------

def _build_therapist_graph():
    g = StateGraph(TherapistState)
    g.add_node("memory_loader", memory_loader_node)
    g.add_node("platform_loader", platform_loader_node)
    g.add_node("therapy_response", therapy_response_node)
    g.add_node("crisis_detector", therapist_crisis_node)
    g.add_node("memory_compactor", memory_compactor_node)

    g.set_entry_point("memory_loader")
    g.add_edge("memory_loader", "platform_loader")
    g.add_edge("platform_loader", "therapy_response")
    g.add_edge("therapy_response", "crisis_detector")
    g.add_edge("crisis_detector", "memory_compactor")
    g.add_edge("memory_compactor", END)

    return g.compile()


_therapist_graph = None


def get_therapist_graph():
    global _therapist_graph
    if _therapist_graph is None:
        _therapist_graph = _build_therapist_graph()
    return _therapist_graph


# ---------------------------------------------------------------------------
# Public streaming API
# ---------------------------------------------------------------------------

async def stream_therapist_response(
    user_id: str,
    session_id: str,
    message: str,
    db: AsyncSession,
) -> AsyncGenerator[dict, None]:
    initial_state: TherapistState = {
        "user_id": user_id,
        "session_id": session_id,
        "message": message,
        "_db": db,  # type: ignore[typeddict-item]
    }

    graph = get_therapist_graph()

    try:
        final_state = await graph.ainvoke(initial_state)
        response_text = final_state.get("response", "I'm here with you.")

        # Stream word by word for natural feel
        words = response_text.split()
        chunk_size = 3
        for i in range(0, len(words), chunk_size):
            chunk = " ".join(words[i:i + chunk_size])
            if i + chunk_size < len(words):
                chunk += " "
            yield {"type": "token", "content": chunk}

        crisis_level = final_state.get("crisis_level", 0)
        if crisis_level >= 2:
            yield {
                "type": "crisis",
                "level": crisis_level,
                "resources": final_state.get("crisis_resources", []),
            }

        yield {"type": "done"}

    except Exception as e:
        logger.error(f"Therapist graph error: {e}")
        fallback = "I'm here with you. Take a moment — you're safe to share whatever feels right."
        yield {"type": "token", "content": fallback}
        yield {"type": "done"}

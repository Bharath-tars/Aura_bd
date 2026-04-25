"""Load user context from DB into state before any agent runs."""
from agents.state import WellnessState
from agents.tools import get_mood_history, get_journal_summary, get_wellness_context, get_graph_insights
import asyncio


async def context_loader_node(state: WellnessState) -> dict:
    uid = state["user_id"]

    try:
        mood_ctx, journal_ctx, wellness_ctx, graph_ctx = await asyncio.gather(
            get_mood_history.ainvoke({"user_id": uid, "days": 14}),
            get_journal_summary.ainvoke({"user_id": uid, "limit": 5}),
            get_wellness_context.ainvoke({"user_id": uid}),
            get_graph_insights.ainvoke({"user_id": uid}),
        )
    except Exception:
        mood_ctx = journal_ctx = wellness_ctx = graph_ctx = {}

    return {
        "mood_context": mood_ctx,
        "journal_context": journal_ctx,
        "wellness_context": wellness_ctx,
        "graph_insights": graph_ctx,
        "routing_path": state.get("routing_path", []) + ["context_loader"],
    }

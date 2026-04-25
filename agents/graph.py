"""
LangGraph state machine — the main AI entry point for Aura.

Flow:
  semantic_router → context_loader → [wellness_coach | mood_analyzer |
                                       journal_insights | plan_generator | crisis_direct]
                 → crisis_detector (always) → response_synthesizer → END

Public API used by routers:
  stream_wellness_response(user_id, session_id, message, db) → AsyncGenerator
  run_journal_analysis(user_id, journal_content, db) → dict
  run_plan_generation(user_id, focus, db) → dict
"""
from __future__ import annotations

import json
import logging
from typing import AsyncGenerator

from langchain_core.messages import HumanMessage
from langgraph.graph import END, StateGraph

from .nodes.context_loader import context_loader_node
from .nodes.crisis_detector import crisis_detector_node
from .nodes.journal_insights import journal_insights_node
from .nodes.mood_analyzer import mood_analyzer_node
from .nodes.plan_generator import plan_generator_node
from .nodes.response_synthesizer import response_synthesizer_node
from .nodes.wellness_coach import wellness_coach_node
from .semantic_router import get_router
from .state import WellnessState

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Routing helpers
# ---------------------------------------------------------------------------

async def semantic_routing_node(state: WellnessState) -> dict:
    """Classify intent using embedding cosine similarity (<50ms, no LLM)."""
    router = get_router()
    user_message = state["messages"][-1].content if state["messages"] else ""

    if router is None:
        return {
            "intent": "coach",
            "intent_confidence": 0.5,
            "routing_path": state.get("routing_path", []) + ["semantic_router"],
        }

    intent, confidence = await router.route(user_message)
    return {
        "intent": intent,
        "intent_confidence": confidence,
        "routing_path": state.get("routing_path", []) + ["semantic_router"],
    }


def _route_by_intent(state: WellnessState) -> str:
    intent = state.get("intent", "coach")
    mapping = {
        "coach": "wellness_coach",
        "mood_analysis": "mood_analyzer",
        "journal_insights": "journal_insights",
        "plan_generation": "plan_generator",
        "crisis": "crisis_detector",
    }
    return mapping.get(intent, "wellness_coach")


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------

def _build_graph() -> StateGraph:
    g = StateGraph(WellnessState)

    g.add_node("semantic_router", semantic_routing_node)
    g.add_node("context_loader", context_loader_node)
    g.add_node("wellness_coach", wellness_coach_node)
    g.add_node("mood_analyzer", mood_analyzer_node)
    g.add_node("journal_insights", journal_insights_node)
    g.add_node("plan_generator", plan_generator_node)
    g.add_node("crisis_detector", crisis_detector_node)
    g.add_node("response_synthesizer", response_synthesizer_node)

    g.set_entry_point("semantic_router")
    g.add_edge("semantic_router", "context_loader")

    g.add_conditional_edges(
        "context_loader",
        _route_by_intent,
        {
            "wellness_coach": "wellness_coach",
            "mood_analyzer": "mood_analyzer",
            "journal_insights": "journal_insights",
            "plan_generator": "plan_generator",
            "crisis_detector": "crisis_detector",
        },
    )

    # All specialist nodes feed into crisis_detector
    for node in ("wellness_coach", "mood_analyzer", "journal_insights", "plan_generator"):
        g.add_edge(node, "crisis_detector")

    g.add_edge("crisis_detector", "response_synthesizer")
    g.add_edge("response_synthesizer", END)

    return g.compile()


# Singleton compiled graph — built once at import time
_compiled_graph = _build_graph()


# ---------------------------------------------------------------------------
# Public streaming API
# ---------------------------------------------------------------------------

async def stream_wellness_response(
    user_id: str,
    session_id: str,
    message: str,
    db,  # AsyncSession — passed through to tools via state
) -> AsyncGenerator[dict, None]:
    """
    Stream tokens and metadata to the SSE endpoint.

    Yields dicts:
      {"type": "token",  "content": str}
      {"type": "crisis", "level": int, "resources": list[str]}
      {"type": "insight","data": list[dict]}
      {"type": "plan",   "data": dict}
      {"type": "done",   "routing_path": list[str], "crisis_level": int}
    """
    initial_state: WellnessState = {
        "messages": [HumanMessage(content=message)],
        "user_id": user_id,
        "session_id": session_id,
        "intent": "",
        "intent_confidence": 0.0,
        "routing_path": [],
        "mood_context": {},
        "journal_context": {},
        "wellness_context": {},
        "graph_insights": {},
        "tool_calls_made": [],
        "tool_results": {},
        "agent_thoughts": [],
        "crisis_level": 0,
        "crisis_resources": [],
        "final_response": "",
        "insights": [],
        "recommendations": [],
        "plan_draft": None,
        "requires_human": False,
    }

    try:
        final_state = await _compiled_graph.ainvoke(initial_state)
    except Exception as exc:
        logger.exception("Graph invocation failed: %s", exc)
        yield {"type": "token", "content": "I'm having trouble processing that right now. Please try again."}
        yield {"type": "done", "routing_path": [], "crisis_level": 0}
        return

    response_text = final_state.get("final_response", "")

    # Stream the response text in word-sized chunks for a natural feel
    words = response_text.split(" ")
    for i, word in enumerate(words):
        chunk = word if i == 0 else " " + word
        yield {"type": "token", "content": chunk}

    crisis_level = final_state.get("crisis_level", 0)
    if crisis_level >= 2:
        yield {
            "type": "crisis",
            "level": crisis_level,
            "resources": final_state.get("crisis_resources", []),
        }

    if final_state.get("insights"):
        yield {"type": "insight", "data": final_state["insights"]}

    if final_state.get("plan_draft"):
        yield {"type": "plan", "data": final_state["plan_draft"]}

    yield {
        "type": "done",
        "routing_path": final_state.get("routing_path", []),
        "crisis_level": crisis_level,
        "requires_human": final_state.get("requires_human", False),
    }


# ---------------------------------------------------------------------------
# One-shot helpers (non-streaming) used by journal and wellness routers
# ---------------------------------------------------------------------------

async def run_journal_analysis(
    user_id: str,
    journal_content: str,
    db,
) -> dict:
    """
    Run the journal_insights node in isolation on provided content.
    Returns {"sentiment_score", "themes", "insights"}.
    """
    state: WellnessState = {
        "messages": [HumanMessage(content=journal_content)],
        "user_id": user_id,
        "session_id": "journal-analysis",
        "intent": "journal_insights",
        "intent_confidence": 1.0,
        "routing_path": [],
        "mood_context": {},
        "journal_context": {},
        "wellness_context": {},
        "graph_insights": {},
        "tool_calls_made": [],
        "tool_results": {},
        "agent_thoughts": [],
        "crisis_level": 0,
        "crisis_resources": [],
        "final_response": "",
        "insights": [],
        "recommendations": [],
        "plan_draft": None,
        "requires_human": False,
    }

    try:
        result = await _compiled_graph.ainvoke(state)
        tool_results = result.get("tool_results", {})
        return {
            "sentiment_score": tool_results.get("sentiment_score"),
            "themes": tool_results.get("themes", []),
            "insights": result.get("insights", []),
            "summary": result.get("final_response", ""),
            "crisis_level": result.get("crisis_level", 0),
        }
    except Exception as exc:
        logger.exception("Journal analysis failed: %s", exc)
        return {"sentiment_score": None, "themes": [], "insights": [], "summary": "", "crisis_level": 0}


async def run_plan_generation(
    user_id: str,
    focus: str,
    db,
) -> dict:
    """
    Run the plan_generator node in isolation.
    Returns the plan_draft dict.
    """
    state: WellnessState = {
        "messages": [HumanMessage(content=focus or "Create a wellness plan for me")],
        "user_id": user_id,
        "session_id": "plan-generation",
        "intent": "plan_generation",
        "intent_confidence": 1.0,
        "routing_path": [],
        "mood_context": {},
        "journal_context": {},
        "wellness_context": {},
        "graph_insights": {},
        "tool_calls_made": [],
        "tool_results": {},
        "agent_thoughts": [],
        "crisis_level": 0,
        "crisis_resources": [],
        "final_response": "",
        "insights": [],
        "recommendations": [],
        "plan_draft": None,
        "requires_human": False,
    }

    try:
        result = await _compiled_graph.ainvoke(state)
        return {
            "plan_draft": result.get("plan_draft", {}),
            "summary": result.get("final_response", ""),
        }
    except Exception as exc:
        logger.exception("Plan generation failed: %s", exc)
        return {"plan_draft": {}, "summary": ""}

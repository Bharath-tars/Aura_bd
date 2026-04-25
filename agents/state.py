from typing import Annotated, TypedDict
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class WellnessState(TypedDict):
    # Conversation
    messages: Annotated[list[BaseMessage], add_messages]
    user_id: str
    session_id: str

    # Routing
    intent: str               # "coach"|"mood_analysis"|"journal_insights"|"plan_generation"|"crisis"
    intent_confidence: float
    routing_path: list[str]   # audit trail of nodes visited

    # Context loaded from DB
    mood_context: dict        # {entries, avg_score, trend, weekly_avgs, top_positive, top_negative}
    journal_context: dict     # {entries, themes, sentiment_trend}
    wellness_context: dict    # {active_plans, completion_rate}
    graph_insights: dict      # semantic graph derived correlations

    # ReAct trace (debug)
    tool_calls_made: list[str]
    tool_results: dict
    agent_thoughts: list[str]

    # Safety
    crisis_level: int         # 0-4
    crisis_resources: list[str]

    # Output
    final_response: str
    insights: list[dict]      # [{title, body, type}]
    recommendations: list[dict]
    plan_draft: dict | None
    requires_human: bool

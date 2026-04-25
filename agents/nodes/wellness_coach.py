"""
Wellness Coach agent node.
Empathetic, CBT-informed conversational AI coach.
Follows one-shot prompting pattern with ReAct reasoning.
"""
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from agents.state import WellnessState
from config import get_settings

SYSTEM_PROMPT = """You are Aura — a compassionate AI wellness companion trained in cognitive-behavioral therapy (CBT), mindfulness-based stress reduction (MBSR), and positive psychology. You are warm, genuine, and science-grounded.

PRINCIPLES:
- Always acknowledge what the person is feeling BEFORE offering anything
- Reference THEIR actual data (mood scores, journal themes, patterns) — never generic advice
- Never diagnose. Never dismiss. Never minimize.
- Keep responses conversational: 2-3 paragraphs maximum
- Always end with ONE concrete, doable micro-action or a genuine question
- If they seem to be struggling: lean in, don't deflect to a checklist

## ONE-SHOT EXAMPLE

Mood context (7d avg): 3.8/10 ↓ trending down from 6.2 three weeks ago
Journal themes: ["work_pressure", "deadline", "not_sleeping", "feeling_alone"]
Positive factor: exercise (+2.3 mood delta based on their data)

User: "I've been feeling really overwhelmed with work and I can't sleep properly."

Response:
"That combination — work pressure bleeding into sleepless nights — is one of the most draining cycles to be caught in. And you've been in it for a few weeks now, based on what I can see. Your body isn't overreacting. It's telling you something is genuinely off.

Looking at your recent patterns, I noticed that on the days you've exercised — even just walking — your mood tends to shift about 2.3 points higher than your average. That's your single strongest lever right now, and it's completely yours to pull.

For tonight, try this: keep your phone out of the bedroom and spend 5 minutes doing 4-7-8 breathing before you sleep (inhale 4 counts, hold 7, exhale 8). It signals your nervous system that the day is actually over. What feels most overwhelming about work right now — is it the volume, the uncertainty, or something else?"

---
Now respond using the user's actual context below."""


async def wellness_coach_node(state: WellnessState) -> dict:
    settings = get_settings()
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key=settings.gemini_api_key,
        temperature=0.7,
        streaming=True,
    )

    mood = state.get("mood_context", {})
    journal = state.get("journal_context", {})
    graph = state.get("graph_insights", {})

    context_summary = f"""User wellness context:
- Mood avg (14d): {mood.get('avg_score', 'unknown')}/10, trend: {mood.get('trend', 'unknown')}
- Top positive factors: {mood.get('top_positive_factors', [])}
- Top negative factors: {mood.get('top_negative_factors', [])}
- Journal themes: {journal.get('top_themes', [])}
- Journal sentiment: {journal.get('sentiment_label', 'unknown')}
- Semantic graph positive levers: {graph.get('positive_levers', [])}
- Active wellness plans: {state.get('wellness_context', {}).get('plan_count', 0)}"""

    user_message = state["messages"][-1].content if state["messages"] else ""

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=f"{context_summary}\n\nUser: {user_message}"),
    ]

    response = await llm.ainvoke(messages)
    final_response = response.content

    return {
        "final_response": final_response,
        "routing_path": state.get("routing_path", []) + ["wellness_coach"],
        "agent_thoughts": state.get("agent_thoughts", []) + [f"coach_responded"],
    }

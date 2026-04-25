"""
Plan Generator agent node.
Evidence-based, progressive wellness plan creation.
"""
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from agents.state import WellnessState
from config import get_settings
import json
import re
from datetime import date, timedelta

SYSTEM_PROMPT = """You are Aura's wellness strategist. You synthesize everything known about the user into a concrete, realistic, personalized wellness plan grounded in CBT, behavioral activation, sleep hygiene research, and habit formation science.

PLAN RULES:
- Start with what they're ALREADY doing right (no cold start shame)
- Week 1-2: only minimum viable habits. Nothing heroic.
- Week 3-4: build on what's working. Add one thing at most.
- Be specific: named activities, durations, frequencies
- Every recommendation must trace back to user's own data

Return as JSON:
{
  "title": "...",
  "description": "...",
  "goals": [{"title": "...", "target": "...", "unit": "...", "current": "0", "deadline": "YYYY-MM-DD"}],
  "activities": [{"name": "...", "frequency": "daily|3x/week|weekly", "duration_min": 10, "category": "mindfulness|physical|social|sleep"}],
  "start_date": "YYYY-MM-DD",
  "end_date": "YYYY-MM-DD"
}

## ONE-SHOT EXAMPLE

User data: mood avg 4.2, exercise (+2.3 delta), no current habits
Stressors: work_deadline, social_isolation
Request: "help me feel less anxious and sleep better"

Output:
{
  "title": "Ground & Reset — 4-Week Foundation",
  "description": "A minimum-viable wellness foundation targeting your two proven mood levers: exercise and better sleep.",
  "goals": [
    {"title": "Raise mood baseline", "target": "6.5", "unit": "/10", "current": "4.2", "deadline": null},
    {"title": "Consistent sleep", "target": "7", "unit": "hours/night", "current": "?", "deadline": null}
  ],
  "activities": [
    {"name": "Morning box breathing", "frequency": "daily", "duration_min": 5, "category": "mindfulness"},
    {"name": "Outdoor walk", "frequency": "daily", "duration_min": 15, "category": "physical"},
    {"name": "Phone-free wind-down", "frequency": "daily", "duration_min": 30, "category": "sleep"},
    {"name": "Social touchpoint", "frequency": "weekly", "duration_min": 30, "category": "social"}
  ],
  "start_date": "TODAY",
  "end_date": "TODAY+28"
}

---
Now generate a plan for the current user based on their data. Return only valid JSON."""


async def plan_generator_node(state: WellnessState) -> dict:
    settings = get_settings()
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key=settings.gemini_api_key,
        temperature=0.4,
    )

    mood = state.get("mood_context", {})
    graph = state.get("graph_insights", {})
    journal = state.get("journal_context", {})
    user_message = state["messages"][-1].content if state["messages"] else "Generate a wellness plan"

    today = date.today().isoformat()
    end = (date.today() + timedelta(days=28)).isoformat()

    context = f"""User data for plan generation:
- Mood avg: {mood.get('avg_score', 'unknown')}/10, trend: {mood.get('trend', 'unknown')}
- Positive mood factors: {mood.get('top_positive_factors', [])}
- Negative mood factors: {mood.get('top_negative_factors', [])}
- Semantic graph levers: {graph.get('positive_levers', [])}
- Journal themes (stressors/interests): {journal.get('top_themes', [])}
- Active plans: {state.get('wellness_context', {}).get('plan_count', 0)}
- Today's date: {today}, suggested end: {end}
- User focus/request: {user_message}"""

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=context),
    ]

    response = await llm.ainvoke(messages)
    raw = response.content.strip()

    plan_data = {}
    try:
        json_match = re.search(r'\{.*\}', raw, re.DOTALL)
        if json_match:
            plan_data = json.loads(json_match.group())
    except Exception:
        plan_data = {"title": "Wellness Plan", "description": "AI-generated plan", "goals": [], "activities": [], "start_date": today, "end_date": end}

    summary = f"I've created '{plan_data.get('title', 'Your Plan')}' for you — {plan_data.get('description', '')} Starting with the minimum viable habits that your data says will work best for you."

    return {
        "final_response": summary,
        "plan_draft": plan_data,
        "routing_path": state.get("routing_path", []) + ["plan_generator"],
    }

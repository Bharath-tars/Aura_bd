"""
Mood Analyzer agent node.
Data-driven pattern analysis with empathetic framing.
"""
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from agents.state import WellnessState
from config import get_settings

SYSTEM_PROMPT = """You are Aura's mood intelligence engine. You analyze emotional patterns with the rigor of a behavioral data scientist and the communication style of an empathetic coach. Find the non-obvious. Name the pattern clearly. Make it actionable.

## ONE-SHOT EXAMPLE

Mood data provided:
avg_score: 5.4, trend: declining
weekly_avgs: [6.8, 5.9, 5.1, 4.2]
top_negative_factors: ["work","poor_sleep","social_isolation"]
top_positive_factors: ["exercise","nature","creative_work"]
positive_levers: [{"factor": "exercise", "delta": 2.3}]

Thought process:
- Average 5.4 masks an alarming trend: 4-week decline from 6.8 → 4.2 (38% drop)
- Anxiety + fatigue dominate. Social isolation is new in last 2 weeks — flag this
- Exercise: +2.3 point lift. That's the strongest personal lever. Quantify it.

Insights to surface:
1. "Your mood has fallen 38% over 4 weeks — this isn't a bad day, it's a trend."
2. "Exercise gives you a +2.3 point mood lift — your most reliable lever."
3. "Social isolation appeared in the last 2 weeks. Loneliness often compounds stress silently."

---
Now analyze the current user's mood data and produce 2-4 specific, personal insights."""


async def mood_analyzer_node(state: WellnessState) -> dict:
    settings = get_settings()
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key=settings.gemini_api_key,
        temperature=0.4,
    )

    mood = state.get("mood_context", {})
    graph = state.get("graph_insights", {})

    data_summary = f"""Mood data for analysis:
- Avg score: {mood.get('avg_score', 'N/A')}/10
- Trend: {mood.get('trend', 'unknown')}
- Weekly avgs (oldest→newest): {mood.get('weekly_avgs', [])}
- Top negative factors: {mood.get('top_negative_factors', [])}
- Top positive factors: {mood.get('top_positive_factors', [])}
- Semantic graph positive levers: {graph.get('positive_levers', [])}
- Emotion frequency: {graph.get('emotion_freq', {})}
- Top journal themes: {state.get('journal_context', {}).get('top_themes', [])}

User message: {state['messages'][-1].content if state['messages'] else 'Show me my mood analysis'}"""

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=data_summary),
    ]

    response = await llm.ainvoke(messages)

    return {
        "final_response": response.content,
        "routing_path": state.get("routing_path", []) + ["mood_analyzer"],
    }

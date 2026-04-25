"""
Journal Insights agent node.
NLP theme extraction, sentiment analysis, pattern revelation.
"""
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from agents.state import WellnessState
from config import get_settings
import json
import re

SYSTEM_PROMPT = """You are Aura's journal intelligence engine. You analyze personal writing with the depth of a narrative therapist and the clarity of a data analyst.

Your job: extract themes, emotional patterns, and non-obvious insights from journal content. Always be kind, never clinical.

Return your analysis as structured JSON:
{
  "sentiment_score": <float -1.0 to 1.0>,
  "themes": ["theme1", "theme2", ...],
  "insights": [
    {"title": "...", "body": "...", "type": "theme|pattern|recommendation|reflection"},
    ...
  ]
}

Rules:
- themes: use snake_case, 2-3 words max each, 3-7 themes
- insights: 2-4 insights, each specific and personal to the content
- sentiment_score: -1.0 (very negative) to 1.0 (very positive)
- insight types: "theme" (recurring idea), "pattern" (behavioral), "recommendation" (gentle suggestion), "reflection" (deeper meaning)

## ONE-SHOT EXAMPLE

Journal entry: "Had another terrible day at work. My manager keeps changing requirements and I feel like nothing I do is good enough. Didn't sleep well again. Called my sister tonight which actually helped. I keep wondering if I'm in the right career."

Output:
{
  "sentiment_score": -0.4,
  "themes": ["work_frustration", "identity_questioning", "support_from_family", "sleep_disruption"],
  "insights": [
    {"title": "Recurring work tension", "body": "Work pressure and feeling unrecognized is a consistent thread. This is worth exploring — is this a temporary phase or a deeper fit issue?", "type": "pattern"},
    {"title": "Your support system is working", "body": "Calling your sister made a difference. That's not small. Human connection is one of your clearest mood levers.", "type": "reflection"},
    {"title": "Career questioning is healthy", "body": "Wondering if you're in the right place isn't a crisis — it's self-awareness. It might be worth journaling specifically about what energizes vs. drains you.", "type": "recommendation"}
  ]
}

---
Now analyze the journal entry provided. Return only valid JSON."""


async def journal_insights_node(state: WellnessState) -> dict:
    settings = get_settings()
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key=settings.gemini_api_key,
        temperature=0.3,
    )

    user_message = state["messages"][-1].content if state["messages"] else ""

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=f"Journal entry to analyze:\n\n{user_message}"),
    ]

    response = await llm.ainvoke(messages)
    raw = response.content.strip()

    # Extract JSON from response
    result = {"sentiment_score": None, "themes": [], "insights": []}
    try:
        json_match = re.search(r'\{.*\}', raw, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
    except Exception:
        pass

    # Format as readable response too
    insight_text = "\n\n".join(
        f"**{ins['title']}**\n{ins['body']}"
        for ins in result.get("insights", [])
    )
    summary = f"Here's what I found in your entry:\n\n{insight_text}" if insight_text else "I analyzed your entry. Keep writing — patterns emerge with more entries."

    return {
        "final_response": summary,
        "insights": result.get("insights", []),
        "routing_path": state.get("routing_path", []) + ["journal_insights"],
        "tool_results": {
            "sentiment_score": result.get("sentiment_score"),
            "themes": result.get("themes", []),
            "insights": result.get("insights", []),
        },
    }

"""
Crisis Detector agent node — always runs last before response synthesis.
Conservative: over-detect rather than under-detect.
Never generates user-facing text — only sets crisis_level and crisis_resources.
"""
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from agents.state import WellnessState
from agents.tools import get_crisis_resources
from config import get_settings
import json
import re

SYSTEM_PROMPT = """You are a safety assessment layer for a mental wellness app.
Assess the LATEST user message for crisis signals.

Return ONLY valid JSON: {"level": <int 0-4>, "reasoning": "<brief>"}

ASSESSMENT SCALE:
  0: No distress signals
  1: Mild/general sadness, stress, overwhelm — normal range
  2: Moderate distress — hopelessness, prolonged sadness, "not coping"
  3: High distress — worthlessness, wishing things were different, resignation
  4: Critical — any mention of self-harm, suicide, not wanting to exist

RULES:
- Err on the side of caution: when uncertain between levels, choose the higher one
- Level 4 triggers if ANY phrase suggests self-harm or suicidal ideation, even indirect

FEW-SHOT EXAMPLES:
"I'm just so tired" → {"level": 1, "reasoning": "general exhaustion"}
"I feel like nothing I do matters anymore" → {"level": 2, "reasoning": "hopelessness signal"}
"I've been thinking everyone would be better off without me" → {"level": 4, "reasoning": "suicidal ideation"}
"I just want all of this to stop" → {"level": 3, "reasoning": "ambiguous high-risk phrasing"}
"help me with my mood patterns" → {"level": 0, "reasoning": "no distress signals"}

Return only the JSON object."""


async def crisis_detector_node(state: WellnessState) -> dict:
    settings = get_settings()

    user_message = state["messages"][-1].content if state["messages"] else ""
    if not user_message.strip():
        return {"crisis_level": 0, "crisis_resources": [], "routing_path": state.get("routing_path", []) + ["crisis_detector"]}

    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key=settings.gemini_api_key,
        temperature=0.1,
    )

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=f"Assess this message: {user_message}"),
    ]

    try:
        response = await llm.ainvoke(messages)
        raw = response.content.strip()
        json_match = re.search(r'\{.*\}', raw, re.DOTALL)
        result = json.loads(json_match.group()) if json_match else {"level": 0}
        level = int(result.get("level", 0))
    except Exception:
        level = 0

    resources: list[str] = []
    requires_human = False
    if level >= 2:
        resources = get_crisis_resources.invoke({"level": level})
    if level >= 4:
        requires_human = True

    return {
        "crisis_level": level,
        "crisis_resources": resources,
        "requires_human": requires_human,
        "routing_path": state.get("routing_path", []) + ["crisis_detector"],
    }

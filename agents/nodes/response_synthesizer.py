"""
Response Synthesizer — final node.
Assembles the final response, injects crisis resources if needed,
formats insights, and prepares the SSE payload structure.
"""
from agents.state import WellnessState


async def response_synthesizer_node(state: WellnessState) -> dict:
    response = state.get("final_response", "")
    crisis_level = state.get("crisis_level", 0)
    crisis_resources = state.get("crisis_resources", [])

    # Inject crisis resources into response if level >= 2
    if crisis_level >= 2 and crisis_resources:
        resource_text = "\n\n---\n*If you'd like to talk to someone right now:*\n"
        resource_text += "\n".join(f"• {r}" for r in crisis_resources[:2])
        response = response + resource_text

    if crisis_level >= 4:
        response = "I hear you, and I want you to know you are not alone.\n\n" + response

    return {
        "final_response": response,
        "routing_path": state.get("routing_path", []) + ["response_synthesizer"],
    }

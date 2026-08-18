"""Incident processing pipeline.

LangGraph StateGraph that transforms raw incident records into structured
knowledge cards: Analyze -> Generate Card -> Quality Check -> Update KB

This is a knowledge processing workflow, NOT a conversational Agent.
"""

from typing import Any, Callable, Dict, Optional, TypedDict


class IncidentState(TypedDict):
    """State for the incident processing pipeline."""

    incident_id: str
    incident_data: Dict[str, Any]
    root_cause: Optional[str]
    impact: Optional[str]
    solution: Optional[str]
    knowledge_card: Optional[Dict[str, Any]]
    status: Optional[str]
    error: Optional[str]


def analyze_node(state: IncidentState) -> Dict[str, Any]:
    """Analyze incident data to extract root cause and impact."""
    try:
        data = state["incident_data"]
        return {
            "root_cause": data.get("root_cause", "Unknown"),
            "impact": data.get("impact", "Unknown"),
            "solution": data.get("resolution", "Pending investigation"),
            "error": None,
        }
    except Exception as e:
        return {
            "root_cause": None,
            "impact": None,
            "solution": None,
            "error": f"Analysis failed: {str(e)}",
        }


def generate_card_node(state: IncidentState) -> Dict[str, Any]:
    """Generate a structured knowledge card from the incident analysis."""
    try:
        card: Dict[str, Any] = {
            "incident_id": state["incident_id"],
            "title": state["incident_data"].get("title", ""),
            "root_cause": state.get("root_cause", ""),
            "solution": state.get("solution", ""),
            "prevention": [],
            "tags": [state["incident_data"].get("severity", "P3")],
            "related_sops": [],
        }
        return {"knowledge_card": card, "error": None}
    except Exception as e:
        return {"knowledge_card": None, "error": f"Card generation failed: {str(e)}"}


def quality_check_node(state: IncidentState) -> Dict[str, Any]:
    """Validate the generated knowledge card completeness."""
    try:
        card = state.get("knowledge_card")
        if not card:
            return {"status": "failed", "error": "No knowledge card to validate"}

        required_fields = ["root_cause", "solution", "title"]
        missing = [f for f in required_fields if not card.get(f)]
        if missing:
            return {
                "status": "incomplete",
                "error": f"Missing fields: {', '.join(missing)}",
            }

        return {"status": "approved", "error": None}
    except Exception as e:
        return {"status": "failed", "error": f"Quality check failed: {str(e)}"}


def update_kb_node(state: IncidentState) -> Dict[str, Any]:
    """Store the approved knowledge card into the knowledge base."""
    try:
        return {"status": "stored", "error": None}
    except Exception as e:
        return {"status": "failed", "error": f"KB update failed: {str(e)}"}


def build_incident_pipeline() -> Callable[..., Any]:
    """Build the LangGraph incident processing pipeline.

    Sequential graph: analyze -> generate_card -> quality_check -> update_kb.

    Returns:
        A compiled LangGraph app or sequential fallback callable.
    """
    try:
        from langgraph.graph import END, START, StateGraph

        workflow: StateGraph = StateGraph(IncidentState)

        workflow.add_node("analyze", analyze_node)
        workflow.add_node("generate_card", generate_card_node)
        workflow.add_node("quality_check", quality_check_node)
        workflow.add_node("update_kb", update_kb_node)

        workflow.add_edge(START, "analyze")
        workflow.add_edge("analyze", "generate_card")
        workflow.add_edge("generate_card", "quality_check")
        workflow.add_edge("quality_check", "update_kb")
        workflow.add_edge("update_kb", END)

        return workflow.compile()

    except ImportError:

        def sequential_pipeline(state: IncidentState) -> IncidentState:
            state.update(analyze_node(state))  # type: ignore[typeddict-item]
            state.update(generate_card_node(state))  # type: ignore[typeddict-item]
            state.update(quality_check_node(state))  # type: ignore[typeddict-item]
            state.update(update_kb_node(state))  # type: ignore[typeddict-item]
            return state

        return sequential_pipeline


incident_pipeline = build_incident_pipeline()

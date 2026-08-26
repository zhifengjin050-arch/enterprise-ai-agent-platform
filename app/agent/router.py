"""Agent router — resolves intent to orchestration strategy.

Simplified routing for the knowledge agent MVP.
In future iterations this could delegate to specialized sub-agents.
"""

from __future__ import annotations

from typing import Literal

# Known intent names from app/query/intent.py
IntentName = Literal[
    "incident_analysis",
    "sop_lookup",
    "architecture_question",
    "configuration_help",
    "general_search",
]


def route_by_intent(intent: str) -> str:
    """Return a routing hint string based on intent.

    Args:
        intent: Recognized intent name.

    Returns:
        Routing descriptor string.
    """
    routing_map = {
        "incident_analysis": "direct_qa",
        "sop_lookup": "direct_qa",
        "architecture_question": "direct_qa",
        "configuration_help": "direct_qa",
        "general_search": "direct_qa",
    }
    return routing_map.get(intent, "direct_qa")

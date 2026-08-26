"""Knowledge Context API - Integration endpoints for Project 1.

Provides knowledge context for external AI agents (primarily Project 1's AI DevOps Agent).
These endpoints are designed to be consumed by other services, not end users.
"""

from fastapi import APIRouter, Query

from app.integration.project1_bridge import Project1Bridge

router = APIRouter(prefix="/api/context", tags=["context"])
bridge = Project1Bridge()


@router.get("/{topic}")
async def get_knowledge_context(topic: str):
    """Get comprehensive knowledge context for a topic.

    This is the primary integration endpoint for Project 1's Agent.
    Returns documents, SOPs, and incidents related to the topic.

    Args:
        topic: The topic or problem to get context for (e.g. 'K8s Pod OOM')

    Returns:
        Formatted context with knowledge docs, SOPs, and incidents.
    """
    # TODO: Implement real knowledge base search
    return bridge.format_knowledge_context(
        topic=topic,
        documents=[
            {
                "title": f"Knowledge about {topic}",
                "content": f"Content about {topic} (placeholder)",
                "doc_type": "general",
                "relevance": 1.0,
            }
        ],
        sops=[],
        incidents=[],
    )


@router.post("/incident")
async def report_incident_from_agent(data: dict):
    """Receive incident report from Project 1's Agent.

    Project 1 calls this endpoint when its Agent detects a problem
    during execution. The incident is recorded and a knowledge card
    is generated.

    Args:
        data: Incident data from Project 1's Agent execution.

    Returns:
        Recorded incident information.
    """
    formatted = bridge.format_incident_from_agent(data)
    # TODO: Persist to database
    return {
        "message": "Incident received from Agent",
        "incident": formatted,
        "acknowledged": True,
    }


@router.get("/search")
async def search_knowledge(
    q: str = Query(..., description="Search query"),
    limit: int = Query(5, ge=1, le=20),
):
    """Simple knowledge search for external agents.

    Lightweight search endpoint optimized for Agent consumption.
    Returns concise results with title, content preview, and type.
    """
    # TODO: Implement real search
    return {
        "query": q,
        "results": [],
        "total": 0,
    }


@router.get("/health/check")
async def check_integration_health():
    """Check if integration dependencies are available.

    Returns connectivity status to Project 1 and external services.
    """
    return {
        "status": "ok",
        "project3": {"status": "ok", "version": "0.3.0"},
        "project1": {"status": "unknown", "note": "Not configured or unreachable"},
        "llm": {"status": "not_configured", "note": "LLM_API_KEY not set"},
        "database": {"status": "not_connected", "note": "Using placeholder storage"},
    }

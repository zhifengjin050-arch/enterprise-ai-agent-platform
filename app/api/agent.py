"""Knowledge Agent API endpoints.

Provides the conversational Q&A interface for the enterprise
knowledge base via the KnowledgeAgent pipeline.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.agent.knowledge_agent import KnowledgeAgent
from app.conversation.memory import memory as conversation_memory

router = APIRouter(prefix="/api/agent", tags=["Agent"])

# Module-level agent instance
_agent: Optional[KnowledgeAgent] = None


def _get_agent() -> KnowledgeAgent:
    """Get or create the singleton KnowledgeAgent."""
    global _agent
    if _agent is None:
        _agent = KnowledgeAgent()
    return _agent


class ChatRequest(BaseModel):
    """Request body for /api/agent/chat."""
    query: str
    conversation_id: Optional[str] = None
    user_id: str = ""


@router.post("/chat")
async def agent_chat(request: ChatRequest) -> Dict[str, Any]:
    """Process a natural language knowledge query.

    Request body:
        query: User's question (required).
        conversation_id: Optional conversation ID for history.
        user_id: Optional user identifier.

    Returns:
        Answer with citations, confidence, and sources.
    """
    query = request.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="query is required")

    agent = _get_agent()
    try:
        result = await agent.ask(
            query=query,
            conversation_id=request.conversation_id,
            user_id=request.user_id,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return result.to_dict()


@router.get("/history/{conversation_id}")
async def get_agent_history(conversation_id: str) -> Dict[str, Any]:
    """Get conversation history.

    Args:
        conversation_id: Conversation UUID.

    Returns:
        Conversation history with messages.
    """
    conv = conversation_memory.get_conversation(conversation_id)
    if conv is None:
        raise HTTPException(
            status_code=404,
            detail=f"Conversation {conversation_id} not found",
        )
    return conv.to_dict()

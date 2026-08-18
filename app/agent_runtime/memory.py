"""Agent Runtime memory — wraps Phase 5 KnowledgeMemory + conversation + DB."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.conversation.memory import ConversationMemory
from app.knowledge.memory import KnowledgeMemory


class AgentMemoryManager:
    """Unified memory manager for Agent Runtime.

    Short-term: last N conversation turns (ConversationMemory)
    Retrieval cache: KnowledgeMemory LRU
    Long-term: optional DB agent_messages persistence
    """

    def __init__(
        self,
        *,
        max_turns: int = 10,
        max_retrievals: int = 20,
    ) -> None:
        self._conversation = ConversationMemory(max_turns=max_turns)
        self._knowledge = KnowledgeMemory(
            max_turns=max_turns,
            max_retrievals=max_retrievals,
        )

    @property
    def conversation(self) -> ConversationMemory:
        return self._conversation

    @property
    def knowledge(self) -> KnowledgeMemory:
        return self._knowledge

    def ensure_conversation(
        self,
        conversation_id: str,
        *,
        user_id: str = "",
        title: str = "Agent Chat",
    ) -> Any:
        conv = self._conversation.get_conversation(conversation_id)
        if conv is None:
            conv = self._conversation.create_conversation(
                conversation_id, user_id=user_id, title=title
            )
        return conv

    def add_user_message(self, conversation_id: str, content: str) -> None:
        self.ensure_conversation(conversation_id)
        self._conversation.add_message(conversation_id, "user", content)

    def add_assistant_message(self, conversation_id: str, content: str) -> None:
        self.ensure_conversation(conversation_id)
        self._conversation.add_message(conversation_id, "assistant", content)

    def prompt_context(self, conversation_id: str) -> str:
        return self._conversation.to_prompt_context(conversation_id)

    async def persist_message(
        self,
        session: Any,
        *,
        conversation_id: str,
        role: str,
        content: str,
        agent_id: Optional[str] = None,
        task_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Persist a message to agent_messages table."""
        from app.agent_runtime.models import AgentMessage

        msg = AgentMessage(
            conversation_id=conversation_id,
            role=role,
            content=content,
            agent_id=agent_id,
            task_id=task_id,
            tenant_id=tenant_id,
            metadata_json=metadata or {},
        )
        session.add(msg)
        await session.flush()
        return msg

    async def list_history(
        self,
        session: Any,
        conversation_id: str,
        *,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Load persisted history for a conversation."""
        from sqlalchemy import select

        from app.agent_runtime.models import AgentMessage

        stmt = (
            select(AgentMessage)
            .where(AgentMessage.conversation_id == conversation_id)
            .order_by(AgentMessage.created_at.asc())
            .limit(limit)
        )
        result = await session.execute(stmt)
        return [m.to_dict() for m in result.scalars().all()]


# Module singleton
agent_memory = AgentMemoryManager()

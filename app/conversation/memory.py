"""Short-term conversation memory.

In-memory store keeping the last N turns per conversation.
Simple MVP implementation — not intended for long-term persistence.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from app.conversation.models import Conversation, ConversationMessage


class ConversationMemory:
    """In-memory conversation memory (last N turns).

    Stores conversations keyed by conversation ID.
    Automatically trims to max_turns to bound memory usage.

    Args:
        max_turns: Maximum messages to retain per conversation (default 10).
    """

    def __init__(self, max_turns: int = 10):
        self._max_turns = max_turns
        self._conversations: Dict[str, Conversation] = {}

    def create_conversation(
        self,
        conversation_id: str,
        user_id: str = "",
        title: str = "New Conversation",
    ) -> Conversation:
        """Create a new conversation session.

        Args:
            conversation_id: Unique identifier.
            user_id: Optional user identifier.
            title: Conversation title.

        Returns:
            The created Conversation.
        """
        conv = Conversation(
            id=conversation_id,
            user_id=user_id,
            title=title,
        )
        self._conversations[conversation_id] = conv
        return conv

    def get_conversation(self, conversation_id: str) -> Optional[Conversation]:
        """Retrieve a conversation by ID.

        Args:
            conversation_id: Conversation identifier.

        Returns:
            Conversation or None if not found.
        """
        return self._conversations.get(conversation_id)

    def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
    ) -> Optional[Conversation]:
        """Add a message to a conversation.

        Auto-creates the conversation if it doesn't exist.
        Trims to max_turns after adding.

        Args:
            conversation_id: Conversation identifier.
            role: "user" or "assistant".
            content: Message text.

        Returns:
            Updated Conversation or None.
        """
        if conversation_id not in self._conversations:
            self.create_conversation(conversation_id)

        conv = self._conversations[conversation_id]
        conv.add_message(role, content)

        # Trim to max_turns
        if len(conv.messages) > self._max_turns:
            conv.messages = conv.messages[-self._max_turns:]

        return conv

    def get_history(
        self,
        conversation_id: str,
        max_turns: Optional[int] = None,
    ) -> List[ConversationMessage]:
        """Get recent conversation history.

        Args:
            conversation_id: Conversation identifier.
            max_turns: Override max turns for this call.

        Returns:
            List of recent messages.
        """
        conv = self._conversations.get(conversation_id)
        if not conv:
            return []
        limit = max_turns or self._max_turns
        return conv.messages[-limit:]

    def to_prompt_context(
        self,
        conversation_id: str,
        max_turns: Optional[int] = None,
    ) -> str:
        """Format conversation history as a prompt context string.

        Args:
            conversation_id: Conversation identifier.
            max_turns: Max turns to include.

        Returns:
            Formatted conversation history string.
        """
        messages = self.get_history(conversation_id, max_turns)
        if not messages:
            return ""

        parts: List[str] = []
        for msg in messages:
            prefix = "用户" if msg.role == "user" else "助手"
            parts.append(f"{prefix}: {msg.content}")
        return "\n".join(parts)

    def delete_conversation(self, conversation_id: str) -> None:
        """Delete a conversation from memory.

        Args:
            conversation_id: Conversation identifier.
        """
        self._conversations.pop(conversation_id, None)

    def clear(self) -> None:
        """Clear all conversations."""
        self._conversations.clear()


# Module-level singleton
memory: ConversationMemory = ConversationMemory()

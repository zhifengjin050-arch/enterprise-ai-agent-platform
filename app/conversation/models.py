"""Conversation data models.

Lightweight in-memory conversation representation for
the knowledge agent chat feature.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class ConversationMessage:
    """A single message in a conversation.

    Attributes:
        role: Message role (user or assistant).
        content: Message content text.
        created_at: Timestamp when the message was created.
    """
    role: str = "user"  # "user" or "assistant"
    content: str = ""
    created_at: Optional[str] = None

    def __post_init__(self) -> None:
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "role": self.role,
            "content": self.content,
            "created_at": self.created_at,
        }


@dataclass
class Conversation:
    """A conversation session.

    Attributes:
        id: Unique conversation identifier.
        user_id: Optional user identifier.
        title: Conversation title (auto-generated from first query).
        messages: List of conversation messages.
        created_at: Creation timestamp.
        updated_at: Last update timestamp.
    """
    id: str = ""
    user_id: str = ""
    title: str = "New Conversation"
    messages: List[ConversationMessage] = field(default_factory=list)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    def __post_init__(self) -> None:
        now = datetime.now(timezone.utc).isoformat()
        if self.created_at is None:
            self.created_at = now
        if self.updated_at is None:
            self.updated_at = now

    def add_message(self, role: str, content: str) -> None:
        """Add a message to the conversation.

        Args:
            role: "user" or "assistant".
            content: Message text.
        """
        self.messages.append(ConversationMessage(role=role, content=content))
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "title": self.title,
            "messages": [m.to_dict() for m in self.messages],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

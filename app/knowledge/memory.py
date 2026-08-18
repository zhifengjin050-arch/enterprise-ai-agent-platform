"""Knowledge memory for the Intelligence Layer.

Wraps short-term ConversationMemory and provides a retrieval-oriented
memory that caches recent query → result pairs for session continuity.
"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.conversation.memory import ConversationMemory


@dataclass
class MemoryEntry:
    """A cached retrieval memory entry."""

    query: str
    results: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class KnowledgeMemory:
    """Session-scoped knowledge retrieval memory.

    Combines:
        - ConversationMemory for chat turns
        - LRU cache of recent retrieval results

    Args:
        max_turns: Max conversation turns to keep.
        max_retrievals: Max cached retrieval entries (LRU).
    """

    def __init__(
        self,
        max_turns: int = 10,
        max_retrievals: int = 20,
    ) -> None:
        self._conversation = ConversationMemory(max_turns=max_turns)
        self._max_retrievals = max_retrievals
        self._retrieval_cache: OrderedDict[str, MemoryEntry] = OrderedDict()

    @property
    def conversation(self) -> ConversationMemory:
        """Access the underlying ConversationMemory."""
        return self._conversation

    def remember_retrieval(
        self,
        session_id: str,
        query: str,
        results: List[Dict[str, Any]],
        *,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Cache a retrieval result for a session.

        Args:
            session_id: Session / conversation ID.
            query: The search query.
            results: Serialized RetrievalResult dicts.
            metadata: Optional extra metadata.
        """
        key = f"{session_id}:{query.strip().lower()}"
        self._retrieval_cache[key] = MemoryEntry(
            query=query,
            results=results,
            metadata=metadata or {},
        )
        self._retrieval_cache.move_to_end(key)
        while len(self._retrieval_cache) > self._max_retrievals:
            self._retrieval_cache.popitem(last=False)

    def recall_retrieval(
        self, session_id: str, query: str
    ) -> Optional[MemoryEntry]:
        """Recall a cached retrieval if present.

        Args:
            session_id: Session ID.
            query: Query string.

        Returns:
            MemoryEntry or None.
        """
        key = f"{session_id}:{query.strip().lower()}"
        entry = self._retrieval_cache.get(key)
        if entry is not None:
            self._retrieval_cache.move_to_end(key)
        return entry

    def clear_session(self, session_id: str) -> None:
        """Clear retrieval cache entries for a session."""
        prefix = f"{session_id}:"
        keys = [k for k in self._retrieval_cache if k.startswith(prefix)]
        for k in keys:
            del self._retrieval_cache[k]


# Module-level singleton for simple use
knowledge_memory = KnowledgeMemory()

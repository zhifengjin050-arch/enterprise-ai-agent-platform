"""Sync mode definitions for connector synchronisation.

Supports three modes:
    FULL:         Re-sync all documents from the external source.
    INCREMENTAL:  Sync only documents changed since the last checkpoint.
    DELTA:        Like incremental but uses server-side delta APIs where available.

Each sync returns a SyncResult with documents, next_cursor, and has_more
for checkpoint-based recovery.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union

from app.connector.base import ConnectorDocument


class SyncMode(str, enum.Enum):
    """Supported synchronisation modes."""

    FULL = "full"
    INCREMENTAL = "incremental"
    DELTA = "delta"


@dataclass
class SyncCursor:
    """Checkpoint cursor for incremental/delta sync operations.

    Attributes:
        value: Opaque cursor value (e.g., updated_at timestamp, page token).
        mode: The sync mode that produced this cursor.
        timestamp: When this cursor was generated.
    """

    value: str
    mode: SyncMode = SyncMode.INCREMENTAL
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a dict for persistence."""
        return {
            "value": self.value,
            "mode": self.mode.value,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SyncCursor:
        """Deserialize from a dict."""
        return cls(
            value=data["value"],
            mode=SyncMode(data.get("mode", SyncMode.INCREMENTAL.value)),
            timestamp=data.get("timestamp", ""),
        )


@dataclass
class SyncResult:
    """Result of a sync operation, including documents and checkpoint data.

    Phase 4 fields:
        documents: List of synced documents.
        next_cursor: Opaque cursor for the next incremental page (preferred).
        has_more: Whether more pages remain to be synced.

    Backward-compatible fields (Phase 3):
        cursor: SyncCursor object (alias; prefer next_cursor).
        total_count: Total number of documents retrieved.
        errors: List of error messages encountered during sync.
    """

    documents: List[ConnectorDocument] = field(default_factory=list)
    next_cursor: Optional[str] = None
    has_more: bool = False
    # Phase 3 compatibility
    cursor: Optional[SyncCursor] = None
    total_count: int = 0
    errors: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Fill derived fields for backward compatibility."""
        if self.total_count == 0 and self.documents:
            self.total_count = len(self.documents)
        # Sync next_cursor <-> cursor.value
        if self.next_cursor and self.cursor is None:
            self.cursor = SyncCursor(value=self.next_cursor)
        elif self.cursor and self.next_cursor is None:
            self.next_cursor = self.cursor.value

    @classmethod
    def from_documents(
        cls,
        documents: List[ConnectorDocument],
        *,
        next_cursor: Optional[str] = None,
        has_more: bool = False,
        errors: Optional[List[str]] = None,
    ) -> SyncResult:
        """Convenience constructor wrapping a plain document list.

        Args:
            documents: Synced documents.
            next_cursor: Optional cursor for the next page.
            has_more: Whether more pages remain.
            errors: Optional error list.

        Returns:
            A SyncResult instance.
        """
        return cls(
            documents=documents,
            next_cursor=next_cursor,
            has_more=has_more,
            total_count=len(documents),
            errors=errors or [],
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a dict."""
        return {
            "documents": [d.to_dict() for d in self.documents],
            "next_cursor": self.next_cursor,
            "has_more": self.has_more,
            "cursor": self.cursor.to_dict() if self.cursor else None,
            "total_count": self.total_count,
            "errors": self.errors[:10],
        }


def normalize_sync_result(
    result: Union[SyncResult, List[ConnectorDocument]],
) -> SyncResult:
    """Normalize a sync() return value to SyncResult.

    Supports both Phase 3 (List[ConnectorDocument]) and Phase 4 (SyncResult)
    return types for gradual migration.

    Args:
        result: Either a SyncResult or a plain document list.

    Returns:
        A SyncResult instance.
    """
    if isinstance(result, SyncResult):
        return result
    return SyncResult.from_documents(list(result))

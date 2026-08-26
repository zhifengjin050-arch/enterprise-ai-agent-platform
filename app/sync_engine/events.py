"""Sync event model for CDC / Webhook / Realtime sync.

Defines SyncEventType and SyncEvent dataclasses used by the SyncEngine
to emit change events as documents are processed.

Event types:
    CREATE:  A new document was discovered and imported.
    UPDATE:  An existing document was modified.
    DELETE:  A document was removed from the source.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional


class SyncEventType(str, enum.Enum):
    """Types of synchronisation change events."""

    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"


@dataclass
class SyncEvent:
    """In-memory sync change event.

    Attributes:
        event_type: CREATE | UPDATE | DELETE.
        document_id: External document ID.
        connector_id: Connector that produced this event.
        sync_job_id: SyncJob that produced this event.
        payload: Optional document snapshot or delta.
        timestamp: When the event was created.
    """

    event_type: SyncEventType
    document_id: str
    connector_id: str = ""
    sync_job_id: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for persistence / API."""
        return {
            "event_type": self.event_type.value,
            "document_id": self.document_id,
            "connector_id": self.connector_id,
            "sync_job_id": self.sync_job_id,
            "payload": self.payload,
            "timestamp": self.timestamp,
        }

    @classmethod
    def create(
        cls,
        document_id: str,
        *,
        connector_id: str = "",
        sync_job_id: str = "",
        payload: Optional[Dict[str, Any]] = None,
    ) -> SyncEvent:
        """Factory for a CREATE event."""
        return cls(
            event_type=SyncEventType.CREATE,
            document_id=document_id,
            connector_id=connector_id,
            sync_job_id=sync_job_id,
            payload=payload or {},
        )

    @classmethod
    def update(
        cls,
        document_id: str,
        *,
        connector_id: str = "",
        sync_job_id: str = "",
        payload: Optional[Dict[str, Any]] = None,
    ) -> SyncEvent:
        """Factory for an UPDATE event."""
        return cls(
            event_type=SyncEventType.UPDATE,
            document_id=document_id,
            connector_id=connector_id,
            sync_job_id=sync_job_id,
            payload=payload or {},
        )

    @classmethod
    def delete(
        cls,
        document_id: str,
        *,
        connector_id: str = "",
        sync_job_id: str = "",
        payload: Optional[Dict[str, Any]] = None,
    ) -> SyncEvent:
        """Factory for a DELETE event."""
        return cls(
            event_type=SyncEventType.DELETE,
            document_id=document_id,
            connector_id=connector_id,
            sync_job_id=sync_job_id,
            payload=payload or {},
        )

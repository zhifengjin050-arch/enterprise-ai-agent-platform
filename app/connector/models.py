"""Connector ORM models: ConnectorConfig and SyncRecord.

Provides persistence for connector configurations and sync operation history.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.db.base import Base


class ConnectorType(str, enum.Enum):
    """Supported external knowledge source types."""

    FEISHU = "feishu"
    YUQUE = "yuque"
    GITLAB = "gitlab"
    CONFLUENCE = "confluence"
    JIRA = "jira"


class SyncStatus(str, enum.Enum):
    """Status of a sync operation."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class ConnectorConfig(Base):
    """Persistent configuration for an external knowledge source connector.

    Attributes:
        id: UUID primary key.
        tenant_id: Tenant isolation key.
        name: Human-readable connector name.
        type: Connector type (feishu, yuque, gitlab, etc.).
        config_json: JSON blob with connector-specific settings.
        enabled: Whether this connector is active.
        last_sync_at: Timestamp of the last successful sync.
        created_at: Creation timestamp.
        updated_at: Last update timestamp.
    """

    __tablename__ = "connector_configs"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    tenant_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Connector type key: feishu, yuque, gitlab, confluence, jira",
    )
    config_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True, default=None)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_sync_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to a serializable dict."""
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "name": self.name,
            "type": self.type,
            "enabled": self.enabled,
            "last_sync_at": self.last_sync_at.isoformat() if self.last_sync_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class SyncRecord(Base):
    """Record of a single sync operation execution.

    Attributes:
        id: UUID primary key.
        connector_id: FK to ConnectorConfig.
        document_id: External document ID that was synced (optional).
        status: Sync result status.
        error: Error message if the sync failed.
        documents_count: Number of documents synced.
        started_at: When the sync started.
        finished_at: When the sync completed.
    """

    __tablename__ = "sync_records"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    connector_id: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        comment="FK to connector_configs.id",
    )
    tenant_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    document_id: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True,
        comment="External document ID (for single-document sync)",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        comment="pending | running | success | failed",
    )
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    documents_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to a serializable dict."""
        return {
            "id": self.id,
            "connector_id": self.connector_id,
            "document_id": self.document_id,
            "status": self.status,
            "error": self.error,
            "documents_count": self.documents_count,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
        }

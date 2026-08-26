"""Enterprise Sync Engine — database models.

Provides SyncJob and SyncCheckpoint ORM models for durable sync
orchestration, incremental cursor tracking, and failure recovery.

SyncJob:     One execution of a sync operation against a connector.
SyncCheckpoint: Persistent cursor for resume-after-failure.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.db.base import Base


class SyncJobStatus(str, enum.Enum):
    """Lifecycle status of a SyncJob."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PARTIAL = "partial"  # Some documents failed but job completed


class SyncJob(Base):
    """Persistent record of a synchronisation job execution.

    Attributes:
        id: UUID primary key.
        tenant_id: Tenant isolation key.
        connector_id: FK to connector_configs.id.
        sync_mode: full | incremental | delta.
        status: Job lifecycle status.
        cursor: Current/resume cursor value.
        total_count: Total documents discovered.
        success_count: Documents successfully processed.
        failed_count: Documents that failed processing.
        started_at: When the job started.
        finished_at: When the job completed.
        error: Error message if the job failed.
        metadata_json: Optional extra metadata (progress, config snapshot).
    """

    __tablename__ = "sync_jobs"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    tenant_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    connector_id: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        index=True,
        comment="FK to connector_configs.id",
    )
    sync_mode: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="full",
        comment="full | incremental | delta",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=SyncJobStatus.PENDING.value,
        comment="pending | running | success | failed | cancelled | partial",
    )
    cursor: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Opaque cursor for incremental resume",
    )
    total_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    success_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    finished_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
        default=None,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a plain dict for API responses."""
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "connector_id": self.connector_id,
            "sync_mode": self.sync_mode,
            "status": self.status,
            "cursor": self.cursor,
            "total_count": self.total_count,
            "success_count": self.success_count,
            "failed_count": self.failed_count,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "error": self.error,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class SyncCheckpoint(Base):
    """Persistent cursor checkpoint for a connector.

    Enables resume-after-failure: when a sync fails mid-way, the last
    successful cursor is stored here so the next run can continue.

    Attributes:
        id: UUID primary key.
        sync_job_id: Optional FK to the SyncJob that produced this checkpoint.
        connector_id: FK to connector_configs.id (unique per connector).
        cursor: Opaque cursor value.
        updated_at: Last update timestamp.
    """

    __tablename__ = "sync_checkpoints"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    sync_job_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        nullable=True,
        index=True,
        comment="FK to sync_jobs.id (optional)",
    )
    connector_id: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        unique=True,
        index=True,
        comment="FK to connector_configs.id — one checkpoint per connector",
    )
    tenant_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    cursor: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Opaque cursor value for resume",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a plain dict."""
        return {
            "id": self.id,
            "sync_job_id": self.sync_job_id,
            "connector_id": self.connector_id,
            "cursor": self.cursor,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class SyncEventRecord(Base):
    """Persisted sync event for audit / CDC / webhook fan-out.

    Attributes:
        id: UUID primary key.
        sync_job_id: FK to sync_jobs.id.
        connector_id: FK to connector_configs.id.
        event_type: create | update | delete.
        document_id: External document ID.
        payload: Event payload (document snapshot or delta).
        created_at: Event timestamp.
    """

    __tablename__ = "sync_events"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    sync_job_id: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        index=True,
    )
    connector_id: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        index=True,
    )
    tenant_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="create | update | delete",
    )
    document_id: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    payload: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a plain dict."""
        return {
            "id": self.id,
            "sync_job_id": self.sync_job_id,
            "connector_id": self.connector_id,
            "event_type": self.event_type,
            "document_id": self.document_id,
            "payload": self.payload,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

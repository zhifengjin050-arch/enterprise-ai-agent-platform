"""Task ORM model for background workflow execution.

Tracks document import tasks processed by background workers.
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.db.base import Base


class TaskStatus(str, enum.Enum):
    """Task execution status."""

    QUEUED = "queued"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class TaskRecord(Base):
    """Background task record for async workflow execution.

    Attributes:
        id: UUID primary key (string).
        task_type: Type of task (e.g., "document_import").
        status: Current execution status.
        payload: JSON input data for the task.
        result: JSON output data after completion.
        error: Error message if failed.
        created_at: Creation timestamp.
        updated_at: Last update timestamp.
    """

    __tablename__ = "task_records"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    task_type: Mapped[str] = mapped_column(
        String(50), nullable=False, default="document_import"
    )
    tenant_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=TaskStatus.QUEUED.value
    )
    payload: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON, nullable=True, default=dict
    )
    result: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON, nullable=True, default=dict
    )
    error: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

"""Workflow ORM models.

Provides persistence for workflow execution state, enabling
resume, audit, and monitoring capabilities.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy import JSON, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class WorkflowRun(Base):
    """Persistent record of a knowledge workflow execution.

    Each row tracks one document's journey through the pipeline,
    enabling resume after failure and historical audit.
    """

    __tablename__ = "workflow_runs"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    workflow_type: Mapped[str] = mapped_column(
        String(32),
        default="knowledge",
        comment="Pipeline type: knowledge | incident",
    )
    document_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        nullable=True,
        comment="The KnowledgeDocument UUID being processed",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        default="pending",
        comment="pending | processing | review | completed | failed",
    )
    current_node: Mapped[Optional[str]] = mapped_column(
        String(32),
        nullable=True,
        comment="Name of the last / current pipeline node",
    )
    state_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
        comment="Snapshot of KnowledgeState at save point",
    )
    error: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Error message if workflow failed",
    )
    tenant_id: Mapped[Optional[str]] = mapped_column(
        String(36), nullable=True
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

    def __repr__(self) -> str:
        return (
            f"<WorkflowRun id={self.id} type={self.workflow_type} "
            f"status={self.status} node={self.current_node}>"
        )

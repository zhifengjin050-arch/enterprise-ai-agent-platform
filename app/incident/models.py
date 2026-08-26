"""
Incident ORM models.

Stores structured incident records and AI-generated knowledge cards
for the enterprise fault experience repository.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import DateTime, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.db.base import Base


class IncidentStatus(str, enum.Enum):
    """Incident lifecycle status."""

    NEW = "new"
    INVESTIGATING = "investigating"
    RESOLVED = "resolved"
    CLOSED = "closed"


class IncidentRecord(Base):
    """Incident experience record."""

    __tablename__ = "incident_records"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    service: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    tenant_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), nullable=True, index=True
    )
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="P2")
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default=IncidentStatus.NEW.value
    )
    root_cause: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resolution: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    impact: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    timeline: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(JSON, nullable=True)
    related_sop_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    knowledge_card: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Compatibility aliases used by older collector/card_generator code
    @property
    def solution(self) -> Optional[str]:
        return self.resolution

    @solution.setter
    def solution(self, value: Optional[str]) -> None:
        self.resolution = value

    @property
    def occurred_at(self) -> datetime:
        return self.created_at

    @property
    def tags(self) -> str:
        """Compatibility: return empty tag string."""
        return ""

    @property
    def duration_minutes(self) -> Optional[int]:
        return None

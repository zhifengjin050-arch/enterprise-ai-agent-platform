"""
SOP ORM models.

Persists structured Standard Operating Procedure templates for
enterprise SOP operations and execution tracking.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import DateTime, Integer, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.db.base import Base


class SOPTemplate(Base):
    """Persistent SOP template definition."""

    __tablename__ = "sop_templates"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sop_id: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tenant_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), nullable=True, index=True
    )
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="P2")
    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    steps: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    rollback: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(JSON, nullable=True)
    prerequisites: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

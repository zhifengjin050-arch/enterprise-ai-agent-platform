"""Prompt template ORM for DB-backed prompt management.

Coexists with static templates in ``app.prompts`` (plural).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import DateTime, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.db.base import Base


class PromptTemplate(Base):
    """Versioned prompt template stored in PostgreSQL / SQLite."""

    __tablename__ = "prompt_templates"
    __table_args__ = (
        UniqueConstraint("name", "version", name="uq_prompt_templates_name_version"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(50), nullable=False, default="1.0.0")
    content: Mapped[str] = mapped_column(Text, nullable=False)
    system_prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    variables_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    metadata_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    tenant_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    def render(self, **kwargs: Any) -> str:
        """Render content with ``{var}`` placeholders."""
        try:
            return self.content.format(**kwargs)
        except KeyError:
            # Partial render: leave missing placeholders
            result = self.content
            for key, value in kwargs.items():
                result = result.replace("{" + key + "}", str(value))
            return result

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "content": self.content,
            "system_prompt": self.system_prompt,
            "variables": self.variables_json or {},
            "metadata": self.metadata_json or {},
            "tenant_id": self.tenant_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

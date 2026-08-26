"""Organization hierarchy: Organization → Department → users."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import DateTime, ForeignKey, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class OrganizationType(str, enum.Enum):
    ENTERPRISE = "enterprise"
    DEPARTMENT = "department"
    TEAM = "team"


class Organization(Base):
    """Enterprise / department / team node.

    Tree via parent_id. Users link via organization_id (optional).
    """

    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    parent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("organizations.id"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    org_type: Mapped[str] = mapped_column(
        String(50), nullable=False, default=OrganizationType.ENTERPRISE.value, index=True
    )
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    parent: Mapped[Optional["Organization"]] = relationship(
        "Organization", remote_side=[id], backref="children"
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": str(self.id),
            "tenant_id": str(self.tenant_id),
            "parent_id": str(self.parent_id) if self.parent_id else None,
            "name": self.name,
            "org_type": self.org_type,
            "description": self.description,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

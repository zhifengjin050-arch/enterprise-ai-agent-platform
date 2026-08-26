"""Quota plan and usage ORM models."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import DateTime, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.db.base import Base


class QuotaPlanName(str, enum.Enum):
    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"


# Default plan limits (tokens / agent runs / storage MB per day)
DEFAULT_PLANS: Dict[str, Dict[str, Any]] = {
    QuotaPlanName.FREE.value: {
        "daily_tokens": 1000,
        "daily_agent_runs": 50,
        "storage_mb": 100,
        "unlimited": False,
    },
    QuotaPlanName.PRO.value: {
        "daily_tokens": 100_000,
        "daily_agent_runs": 1000,
        "storage_mb": 10_000,
        "unlimited": False,
    },
    QuotaPlanName.ENTERPRISE.value: {
        "daily_tokens": 0,
        "daily_agent_runs": 0,
        "storage_mb": 0,
        "unlimited": True,
    },
}


class QuotaPlan(Base):
    """Tenant quota plan assignment."""

    __tablename__ = "quotas"
    __table_args__ = (UniqueConstraint("tenant_id", name="uq_quotas_tenant_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    plan: Mapped[str] = mapped_column(
        String(50), nullable=False, default=QuotaPlanName.FREE.value, index=True
    )
    daily_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=1000)
    daily_agent_runs: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    storage_mb: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    unlimited: Mapped[bool] = mapped_column(nullable=False, default=False)
    # Usage counters reset daily
    used_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    used_agent_runs: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    used_storage_mb: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    usage_date: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)  # YYYY-MM-DD
    metadata_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "plan": self.plan,
            "daily_tokens": self.daily_tokens,
            "daily_agent_runs": self.daily_agent_runs,
            "storage_mb": self.storage_mb,
            "unlimited": self.unlimited,
            "used_tokens": self.used_tokens,
            "used_agent_runs": self.used_agent_runs,
            "used_storage_mb": self.used_storage_mb,
            "usage_date": self.usage_date,
        }

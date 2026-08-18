"""Observability ORM models: agent_execution_traces, system_events, llm_usage_records."""
from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.db.base import Base


class AgentExecutionTrace(Base):
    """Step-level agent execution trace record."""

    __tablename__ = "agent_execution_traces"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    task_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    tenant_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    step: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    component: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    input_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    output_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    success: Mapped[bool] = mapped_column(nullable=False, default=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "task_id": self.task_id,
            "tenant_id": self.tenant_id,
            "step": self.step,
            "component": self.component,
            "input": self.input_json,
            "output": self.output_json,
            "latency_ms": self.latency_ms,
            "success": self.success,
            "error": self.error,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class LLMUsageRecord(Base):
    """Per-call LLM usage (input/output tokens, cost, attribution)."""

    __tablename__ = "llm_usage_records"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    tenant_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    user_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    agent_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    task_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    provider: Mapped[str] = mapped_column(String(50), nullable=False, default="unknown")
    model: Mapped[str] = mapped_column(String(100), nullable=False, default="unknown")
    request_type: Mapped[str] = mapped_column(String(50), nullable=False, default="other")
    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    estimated_cost: Mapped[float] = mapped_column(nullable=False, default=0.0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "agent_id": self.agent_id,
            "task_id": self.task_id,
            "provider": self.provider,
            "model": self.model,
            "request_type": self.request_type,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "estimated_cost": self.estimated_cost,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class SystemEventType(str, enum.Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    ALERT = "alert"


class SystemEvent(Base):
    """System-level event for alerting / monitoring."""

    __tablename__ = "system_events"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    event_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default=SystemEventType.INFO.value, index=True
    )
    component: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    details_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    tenant_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="info")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "event_type": self.event_type,
            "component": self.component,
            "message": self.message,
            "details": self.details_json,
            "tenant_id": self.tenant_id,
            "severity": self.severity,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

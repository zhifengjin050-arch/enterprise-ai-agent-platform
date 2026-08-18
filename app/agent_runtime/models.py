"""Agent Runtime ORM models and result DTOs.

Tables:
    agents, agent_tasks, agent_messages, agent_tool_calls

DTOs:
    AgentResult, ExecutionPlan, PlanStep
"""

from __future__ import annotations

import enum
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.db.base import Base


class AgentStatus(str, enum.Enum):
    """Lifecycle status of a BaseAgent instance."""

    CREATED = "created"
    INITIALIZED = "initialized"
    RUNNING = "running"
    WAITING = "waiting"
    COMPLETED = "completed"
    FAILED = "failed"


class AgentTaskStatus(str, enum.Enum):
    """Status of a persisted AgentTask."""

    PENDING = "pending"
    RUNNING = "running"
    WAITING = "waiting"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# ── ORM ──


class AgentRecord(Base):
    """Registered agent instance configuration."""

    __tablename__ = "agents"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    tenant_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    agent_type: Mapped[str] = mapped_column(
        String(50), nullable=False, default="knowledge", index=True
    )
    config_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    enabled: Mapped[bool] = mapped_column(nullable=False, default=True)
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
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "name": self.name,
            "agent_type": self.agent_type,
            "enabled": self.enabled,
            "config_json": self.config_json or {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class AgentTask(Base):
    """A single agent execution task."""

    __tablename__ = "agent_tasks"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    tenant_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    agent_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("agents.id"), nullable=True, index=True
    )
    user_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    agent_type: Mapped[str] = mapped_column(String(50), nullable=False, default="knowledge")
    input_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=AgentTaskStatus.PENDING.value, index=True
    )
    result_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "agent_id": self.agent_id,
            "user_id": self.user_id,
            "agent_type": self.agent_type,
            "input": self.input_json or {},
            "status": self.status,
            "result": self.result_json,
            "error": self.error,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class AgentMessage(Base):
    """Persisted conversation message for an agent task / session."""

    __tablename__ = "agent_messages"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    tenant_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    agent_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("agents.id"), nullable=True, index=True
    )
    task_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("agent_tasks.id"), nullable=True, index=True
    )
    conversation_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # user|assistant|system|tool
    content: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "conversation_id": self.conversation_id,
            "task_id": self.task_id,
            "role": self.role,
            "content": self.content,
            "metadata": self.metadata_json or {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class AgentToolCall(Base):
    """Record of a tool invocation during agent execution."""

    __tablename__ = "agent_tool_calls"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    tenant_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    task_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("agent_tasks.id"), nullable=False, index=True
    )
    tool_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    input_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    output_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="success")
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "task_id": self.task_id,
            "tool_name": self.tool_name,
            "input": self.input_json or {},
            "output": self.output_json,
            "status": self.status,
            "latency_ms": self.latency_ms,
            "error": self.error,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# ── DTOs ──


@dataclass
class PlanStep:
    """A single step in an ExecutionPlan."""

    step: int
    tool: str
    input: Dict[str, Any] = field(default_factory=dict)
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step": self.step,
            "tool": self.tool,
            "input": self.input,
            "description": self.description,
        }


@dataclass
class ExecutionPlan:
    """Ordered plan produced by TaskPlanner."""

    steps: List[PlanStep] = field(default_factory=list)
    query: str = ""
    rationale: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "rationale": self.rationale,
            "steps": [s.to_dict() for s in self.steps],
        }


@dataclass
class AgentResult:
    """Result of an agent execution."""

    success: bool = True
    answer: str = ""
    sources: List[Dict[str, Any]] = field(default_factory=list)
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    task_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "answer": self.answer,
            "sources": self.sources,
            "tool_calls": self.tool_calls,
            "metadata": self.metadata,
            "task_id": self.task_id,
        }

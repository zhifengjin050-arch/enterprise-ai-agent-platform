"""Workflow Engine ORM models — Phase 9.

Tables:
    workflows          — Workflow definitions (JSON DSL)
    workflow_nodes     — Individual node definitions
    workflow_executions — Execution records
    workflow_events    — Event log / audit trail

Supports tenant_id, RBAC, and full audit.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    JSON,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

# ──────────────────────────────────────────────
# Enums
# ──────────────────────────────────────────────


class WorkflowStatus(str, enum.Enum):
    CREATED = "CREATED"
    RUNNING = "RUNNING"
    WAITING = "WAITING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class NodeType(str, enum.Enum):
    TRIGGER = "trigger"
    AGENT = "agent"
    TOOL = "tool"
    CONDITION = "condition"
    APPROVAL = "approval"
    END = "end"


class TriggerType(str, enum.Enum):
    API = "api"
    WEBHOOK = "webhook"
    SCHEDULE = "schedule"
    SYNC_EVENT = "sync_event"


class ApprovalStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    TIMEOUT = "TIMEOUT"


# ──────────────────────────────────────────────
# Workflow Definition
# ──────────────────────────────────────────────


class WorkflowDefinition(Base):
    """A workflow definition — the top-level entity.

    Stores the name, JSON DSL definition, and runtime metadata.
    """

    __tablename__ = "workflows"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(128), nullable=False, comment="Workflow display name")
    description: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="Optional description"
    )
    version: Mapped[str] = mapped_column(String(16), default="1.0", comment="DSL schema version")
    definition: Mapped[Dict[str, Any]] = mapped_column(
        JSON, nullable=False, comment="Full JSON DSL definition"
    )
    status: Mapped[WorkflowStatus] = mapped_column(
        Enum(WorkflowStatus),
        default=WorkflowStatus.CREATED,
        comment="Current workflow status",
    )
    trigger_type: Mapped[Optional[TriggerType]] = mapped_column(
        Enum(TriggerType), nullable=True, comment="Associated trigger type"
    )
    trigger_config: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON, nullable=True, comment="Trigger configuration (cron, webhook secret, etc.)"
    )
    timeout_seconds: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="Max execution time in seconds"
    )
    max_retries: Mapped[int] = mapped_column(Integer, default=0, comment="Max retry on failure")
    tags: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True, comment="Tags")

    # Multi-tenant
    tenant_id: Mapped[Optional[str]] = mapped_column(
        String(36), nullable=True, index=True, comment="Tenant isolation"
    )

    # Audit
    created_by: Mapped[Optional[str]] = mapped_column(
        String(128), nullable=True, comment="Creator user ID"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    nodes: Mapped[List["WorkflowNode"]] = relationship(
        "WorkflowNode", back_populates="workflow", cascade="all, delete-orphan"
    )
    runs: Mapped[List["WorkflowExecution"]] = relationship(
        "WorkflowExecution", back_populates="workflow", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_workflows_tenant_status", "tenant_id", "status"),
        Index("ix_workflows_trigger_type", "trigger_type"),
    )

    def __repr__(self) -> str:
        return f"<WorkflowDefinition id={self.id} name={self.name} status={self.status}>"


# ──────────────────────────────────────────────
# Workflow Node
# ──────────────────────────────────────────────


class WorkflowNode(Base):
    """A single node within a workflow definition.

    Stores the node type, configuration, and graph edges.
    """

    __tablename__ = "workflow_nodes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workflow_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False
    )
    node_type: Mapped[NodeType] = mapped_column(Enum(NodeType), nullable=False, comment="Node type")
    node_name: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="Unique node name within workflow"
    )
    label: Mapped[Optional[str]] = mapped_column(
        String(128), nullable=True, comment="Display label"
    )
    config: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON, nullable=True, comment="Node-specific config (agent name, tool name, condition, etc.)"
    )
    next_nodes: Mapped[Optional[List[str]]] = mapped_column(
        JSON, nullable=True, comment="List of next node names (edges)"
    )
    condition_expression: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="Python expression for condition nodes"
    )
    timeout_seconds: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="Per-node timeout"
    )
    retry_count: Mapped[int] = mapped_column(Integer, default=0, comment="Retry attempts")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, comment="Display ordering")

    # Multi-tenant
    tenant_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)

    # Audit
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relationship
    workflow: Mapped["WorkflowDefinition"] = relationship(
        "WorkflowDefinition", back_populates="nodes"
    )

    __table_args__ = (
        UniqueConstraint("workflow_id", "node_name", name="uq_workflow_node_name"),
        Index("ix_workflow_nodes_type", "node_type"),
    )

    def __repr__(self) -> str:
        return f"<WorkflowNode id={self.id} name={self.node_name} type={self.node_type}>"


# ──────────────────────────────────────────────
# Workflow Run (Execution Record)
# ──────────────────────────────────────────────


class WorkflowExecution(Base):
    """An execution record for a workflow.

    Each row tracks one invocation, from trigger through completion.
    """

    __tablename__ = "workflow_executions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workflow_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False
    )
    workflow_name: Mapped[Optional[str]] = mapped_column(
        String(128), nullable=True, comment="Snapshot of workflow name"
    )
    status: Mapped[WorkflowStatus] = mapped_column(
        Enum(WorkflowStatus), default=WorkflowStatus.CREATED, comment="Run status"
    )
    trigger_type: Mapped[Optional[TriggerType]] = mapped_column(Enum(TriggerType), nullable=True)
    trigger_event_id: Mapped[Optional[str]] = mapped_column(
        String(128), nullable=True, comment="External event ID that triggered this run"
    )
    current_node: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True, comment="Current / last executed node name"
    )
    node_results: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON, nullable=True, comment="Map of node_name -> result"
    )
    context: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON, nullable=True, comment="Runtime context / state"
    )
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="Error message")
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="Execution duration in milliseconds"
    )
    retry_count: Mapped[int] = mapped_column(Integer, default=0)

    # Multi-tenant
    tenant_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)

    # Audit
    triggered_by: Mapped[Optional[str]] = mapped_column(
        String(128), nullable=True, comment="User or system that triggered"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    workflow: Mapped["WorkflowDefinition"] = relationship(
        "WorkflowDefinition", back_populates="runs"
    )
    events: Mapped[List["WorkflowEvent"]] = relationship(
        "WorkflowEvent", back_populates="run", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_workflow_exec_tenant_status", "tenant_id", "status"),
        Index("ix_workflow_exec_workflow_status", "workflow_id", "status"),
    )

    def __repr__(self) -> str:
        return f"<WorkflowExecution id={self.id} status={self.status}>"


# ──────────────────────────────────────────────
# Workflow Event (Audit / Event Log)
# ──────────────────────────────────────────────


class WorkflowEvent(Base):
    """Audit event log for workflow execution.

    Records every significant state transition and decision.
    """

    __tablename__ = "workflow_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workflow_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False
    )
    run_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("workflow_executions.id", ondelete="SET NULL"), nullable=True
    )
    node_name: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True, comment="Node that produced the event"
    )
    event_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        comment="node_start | node_end | pause | resume | cancel | error | approval | decision",
    )
    event_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON, nullable=True, comment="Event payload"
    )
    severity: Mapped[str] = mapped_column(String(16), default="info", comment="info | warn | error")

    # Multi-tenant
    tenant_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)

    # Audit
    created_by: Mapped[Optional[str]] = mapped_column(
        String(128), nullable=True, comment="User or system that generated the event"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    run: Mapped[Optional["WorkflowExecution"]] = relationship(
        "WorkflowExecution", back_populates="events"
    )

    __table_args__ = (
        Index("ix_workflow_events_run", "run_id"),
        Index("ix_workflow_events_type", "event_type"),
        Index("ix_workflow_events_created", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<WorkflowEvent id={self.id} type={self.event_type}>"

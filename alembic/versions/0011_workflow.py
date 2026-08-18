"""Phase 9 Workflow Engine: workflows, workflow_nodes, workflow_executions, workflow_events.

Revision ID: 0011
Revises: 0010
Create Date: 2026-08-18
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import sqlite

revision: str = "0011"
down_revision: str = "0010"
branch_labels: None = None
depends_on: None = None


def upgrade() -> None:
    # ### workflows
    op.create_table(
        "workflows",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("version", sa.String(16), nullable=False, server_default="1.0"),
        sa.Column("definition", sa.JSON, nullable=False),
        sa.Column(
            "status",
            sa.Enum("CREATED", "RUNNING", "WAITING", "PAUSED", "COMPLETED", "FAILED", name="workflowstatus"),
            nullable=False,
            server_default="CREATED",
        ),
        sa.Column(
            "trigger_type",
            sa.Enum("api", "webhook", "schedule", "sync_event", name="triggertype"),
            nullable=True,
        ),
        sa.Column("trigger_config", sa.JSON, nullable=True),
        sa.Column("timeout_seconds", sa.Integer, nullable=True),
        sa.Column("max_retries", sa.Integer, nullable=False, server_default="0"),
        sa.Column("tags", sa.JSON, nullable=True),
        sa.Column("tenant_id", sa.String(36), nullable=True, index=True),
        sa.Column("created_by", sa.String(128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_workflows_tenant_status", "workflows", ["tenant_id", "status"])
    op.create_index("ix_workflows_trigger_type", "workflows", ["trigger_type"])

    # ### workflow_nodes
    op.create_table(
        "workflow_nodes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workflow_id", sa.String(36), sa.ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "node_type",
            sa.Enum("trigger", "agent", "tool", "condition", "approval", "end", name="nodetype"),
            nullable=False,
        ),
        sa.Column("node_name", sa.String(64), nullable=False),
        sa.Column("label", sa.String(128), nullable=True),
        sa.Column("config", sa.JSON, nullable=True),
        sa.Column("next_nodes", sa.JSON, nullable=True),
        sa.Column("condition_expression", sa.Text, nullable=True),
        sa.Column("timeout_seconds", sa.Integer, nullable=True),
        sa.Column("retry_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("tenant_id", sa.String(36), nullable=True, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("workflow_id", "node_name", name="uq_workflow_node_name"),
    )
    op.create_index("ix_workflow_nodes_type", "workflow_nodes", ["node_type"])

    # ### workflow_executions (was workflow_runs in old table — separate name to avoid collision)
    op.create_table(
        "workflow_executions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workflow_id", sa.String(36), sa.ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False),
        sa.Column("workflow_name", sa.String(128), nullable=True),
        sa.Column(
            "status",
            sa.Enum("CREATED", "RUNNING", "WAITING", "PAUSED", "COMPLETED", "FAILED", name="workflowstatus"),
            nullable=False,
            server_default="CREATED",
        ),
        sa.Column(
            "trigger_type",
            sa.Enum("api", "webhook", "schedule", "sync_event", name="triggertype"),
            nullable=True,
        ),
        sa.Column("trigger_event_id", sa.String(128), nullable=True),
        sa.Column("current_node", sa.String(64), nullable=True),
        sa.Column("node_results", sa.JSON, nullable=True),
        sa.Column("context", sa.JSON, nullable=True),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Float, nullable=True),
        sa.Column("retry_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("tenant_id", sa.String(36), nullable=True, index=True),
        sa.Column("triggered_by", sa.String(128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_workflow_exec_tenant_status", "workflow_executions", ["tenant_id", "status"])
    op.create_index("ix_workflow_exec_workflow_status", "workflow_executions", ["workflow_id", "status"])

    # ### workflow_events
    op.create_table(
        "workflow_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workflow_id", sa.String(36), sa.ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False),
        sa.Column("run_id", sa.String(36), sa.ForeignKey("workflow_executions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("node_name", sa.String(64), nullable=True),
        sa.Column("event_type", sa.String(32), nullable=False),
        sa.Column("event_data", sa.JSON, nullable=True),
        sa.Column("severity", sa.String(16), nullable=False, server_default="info"),
        sa.Column("tenant_id", sa.String(36), nullable=True, index=True),
        sa.Column("created_by", sa.String(128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_workflow_events_run", "workflow_events", ["run_id"])
    op.create_index("ix_workflow_events_type", "workflow_events", ["event_type"])
    op.create_index("ix_workflow_events_created", "workflow_events", ["created_at"])


def downgrade() -> None:
    op.drop_table("workflow_events")
    op.drop_table("workflow_executions")
    op.drop_table("workflow_nodes")
    op.drop_table("workflows")
    # Note: Enum types are cleaned up by the database when the last
    # referencing table is dropped (PostgreSQL) or are not applicable (SQLite).
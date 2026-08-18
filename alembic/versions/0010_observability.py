"""Phase 8 Observability: llm_usage_records, agent_execution_traces, system_events.

Revision ID: 0010
Revises: 0009
Create Date: 2026-08-18
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import sqlite

revision: str = "0010"
down_revision: str = "0009"
branch_labels: None = None
depends_on: None = None


def upgrade() -> None:
    # ### llm_usage_records (new richer usage table)
    op.create_table(
        "llm_usage_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=True, index=True),
        sa.Column("user_id", sa.String(36), nullable=True, index=True),
        sa.Column("agent_id", sa.String(36), nullable=True, index=True),
        sa.Column("task_id", sa.String(36), nullable=True, index=True),
        sa.Column("provider", sa.String(50), nullable=False, default="unknown"),
        sa.Column("model", sa.String(100), nullable=False, default="unknown"),
        sa.Column("request_type", sa.String(50), nullable=False, default="other"),
        sa.Column("prompt_tokens", sa.Integer, nullable=False, default=0),
        sa.Column("completion_tokens", sa.Integer, nullable=False, default=0),
        sa.Column("total_tokens", sa.Integer, nullable=False, default=0),
        sa.Column("estimated_cost", sa.Float, nullable=False, default=0.0),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            index=True,
        ),
    )

    # ### agent_execution_traces
    op.create_table(
        "agent_execution_traces",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("task_id", sa.String(36), nullable=False, index=True),
        sa.Column("tenant_id", sa.String(36), nullable=True, index=True),
        sa.Column("step", sa.Integer, nullable=False, default=0),
        sa.Column("component", sa.String(50), nullable=False, index=True),
        sa.Column("input_json", sa.JSON, nullable=True),
        sa.Column("output_json", sa.JSON, nullable=True),
        sa.Column("latency_ms", sa.Integer, nullable=True),
        sa.Column("success", sa.Boolean, nullable=False, default=True),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            index=True,
        ),
    )

    # ### system_events (alerting / event records)
    op.create_table(
        "system_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("event_type", sa.String(20), nullable=False, index=True),
        sa.Column("component", sa.String(100), nullable=False, index=True),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("details_json", sa.JSON, nullable=True),
        sa.Column("tenant_id", sa.String(36), nullable=True, index=True),
        sa.Column("severity", sa.String(20), nullable=False, default="info"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            index=True,
        ),
    )


def downgrade() -> None:
    op.drop_table("system_events")
    op.drop_table("agent_execution_traces")
    op.drop_table("llm_usage_records")
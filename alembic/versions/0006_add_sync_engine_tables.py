"""add sync_jobs, sync_checkpoints, sync_events tables

Revision ID: 0006_add_sync_engine_tables
Revises: 0005_add_connector_tables
Create Date: 2026-08-18
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006_add_sync_engine_tables"
down_revision: Union[str, None] = "0005_add_connector_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Sync Jobs ──
    op.create_table(
        "sync_jobs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=True),
        sa.Column("connector_id", sa.String(length=36), nullable=False),
        sa.Column("sync_mode", sa.String(length=20), nullable=False, server_default="full"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("cursor", sa.Text(), nullable=True),
        sa.Column("total_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("success_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sync_jobs_tenant_id", "sync_jobs", ["tenant_id"])
    op.create_index("ix_sync_jobs_connector_id", "sync_jobs", ["connector_id"])

    # ── Sync Checkpoints ──
    op.create_table(
        "sync_checkpoints",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("sync_job_id", sa.String(length=36), nullable=True),
        sa.Column("connector_id", sa.String(length=36), nullable=False),
        sa.Column("cursor", sa.Text(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("connector_id"),
    )
    op.create_index("ix_sync_checkpoints_sync_job_id", "sync_checkpoints", ["sync_job_id"])
    op.create_index("ix_sync_checkpoints_connector_id", "sync_checkpoints", ["connector_id"])

    # ── Sync Events ──
    op.create_table(
        "sync_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("sync_job_id", sa.String(length=36), nullable=False),
        sa.Column("connector_id", sa.String(length=36), nullable=False),
        sa.Column("event_type", sa.String(length=20), nullable=False),
        sa.Column("document_id", sa.String(length=200), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sync_events_sync_job_id", "sync_events", ["sync_job_id"])
    op.create_index("ix_sync_events_connector_id", "sync_events", ["connector_id"])


def downgrade() -> None:
    op.drop_index("ix_sync_events_connector_id", table_name="sync_events")
    op.drop_index("ix_sync_events_sync_job_id", table_name="sync_events")
    op.drop_table("sync_events")

    op.drop_index("ix_sync_checkpoints_connector_id", table_name="sync_checkpoints")
    op.drop_index("ix_sync_checkpoints_sync_job_id", table_name="sync_checkpoints")
    op.drop_table("sync_checkpoints")

    op.drop_index("ix_sync_jobs_connector_id", table_name="sync_jobs")
    op.drop_index("ix_sync_jobs_tenant_id", table_name="sync_jobs")
    op.drop_table("sync_jobs")
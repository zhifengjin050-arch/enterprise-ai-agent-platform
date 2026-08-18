"""enterprise security: organizations, api_keys, audit_logs, quotas + tenant_id columns

Revision ID: 0009_enterprise_security
Revises: 0008_agent_runtime
Create Date: 2026-08-18
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0009_enterprise_security"
down_revision: Union[str, None] = "0008_agent_runtime"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── organizations ──
    op.create_table(
        "organizations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("parent_id", sa.Uuid(), nullable=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("org_type", sa.String(length=50), nullable=False, server_default="enterprise"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["parent_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_organizations_tenant_id", "organizations", ["tenant_id"])
    op.create_index("ix_organizations_parent_id", "organizations", ["parent_id"])
    op.create_index("ix_organizations_org_type", "organizations", ["org_type"])

    # users.organization_id
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("organization_id", sa.Uuid(), nullable=True))
        batch.create_foreign_key(
            "fk_users_organization_id",
            "organizations",
            ["organization_id"],
            ["id"],
        )
        batch.create_index("ix_users_organization_id", ["organization_id"])

    # agent_tasks.user_id
    with op.batch_alter_table("agent_tasks") as batch:
        batch.add_column(sa.Column("user_id", sa.String(length=36), nullable=True))
        batch.create_index("ix_agent_tasks_user_id", ["user_id"])

    # ── api_keys ──
    op.create_table(
        "api_keys",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("key_prefix", sa.String(length=16), nullable=False),
        sa.Column("key_hash", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_api_keys_tenant_id", "api_keys", ["tenant_id"])
    op.create_index("ix_api_keys_key_prefix", "api_keys", ["key_prefix"])
    op.create_index("ix_api_keys_status", "api_keys", ["status"])

    # ── audit_logs ──
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=True),
        sa.Column("user_id", sa.String(length=36), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("resource", sa.String(length=200), nullable=True),
        sa.Column("resource_id", sa.String(length=100), nullable=True),
        sa.Column("ip", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=300), nullable=True),
        sa.Column("details_json", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_logs_tenant_id", "audit_logs", ["tenant_id"])
    op.create_index("ix_audit_logs_user_id", "audit_logs", ["user_id"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_resource", "audit_logs", ["resource"])
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])

    # ── quotas ──
    op.create_table(
        "quotas",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("plan", sa.String(length=50), nullable=False, server_default="free"),
        sa.Column("daily_tokens", sa.Integer(), nullable=False, server_default="1000"),
        sa.Column("daily_agent_runs", sa.Integer(), nullable=False, server_default="50"),
        sa.Column("storage_mb", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("unlimited", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("used_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("used_agent_runs", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("used_storage_mb", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("usage_date", sa.String(length=10), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", name="uq_quotas_tenant_id"),
    )
    op.create_index("ix_quotas_tenant_id", "quotas", ["tenant_id"])
    op.create_index("ix_quotas_plan", "quotas", ["plan"])

    # ── additive tenant_id columns ──
    _add_tenant_str("document_chunks")
    _add_tenant_uuid("categories")
    _add_tenant_uuid("tags")
    _add_tenant_str("sync_checkpoints")
    _add_tenant_str("sync_events")
    _add_tenant_str("sync_records")
    _add_tenant_uuid("sop_templates")
    _add_tenant_uuid("incident_records")
    _add_tenant_str("task_records")
    _add_tenant_str("llm_cost_records")


def _add_tenant_str(table: str) -> None:
    with op.batch_alter_table(table) as batch:
        batch.add_column(sa.Column("tenant_id", sa.String(length=36), nullable=True))
        batch.create_index(f"ix_{table}_tenant_id", ["tenant_id"])


def _add_tenant_uuid(table: str) -> None:
    with op.batch_alter_table(table) as batch:
        batch.add_column(sa.Column("tenant_id", sa.Uuid(), nullable=True))
        batch.create_index(f"ix_{table}_tenant_id", ["tenant_id"])


def downgrade() -> None:
    for table in (
        "llm_cost_records",
        "task_records",
        "incident_records",
        "sop_templates",
        "sync_records",
        "sync_events",
        "sync_checkpoints",
        "tags",
        "categories",
        "document_chunks",
    ):
        with op.batch_alter_table(table) as batch:
            batch.drop_index(f"ix_{table}_tenant_id")
            batch.drop_column("tenant_id")

    op.drop_index("ix_quotas_plan", table_name="quotas")
    op.drop_index("ix_quotas_tenant_id", table_name="quotas")
    op.drop_table("quotas")

    op.drop_index("ix_audit_logs_created_at", table_name="audit_logs")
    op.drop_index("ix_audit_logs_resource", table_name="audit_logs")
    op.drop_index("ix_audit_logs_action", table_name="audit_logs")
    op.drop_index("ix_audit_logs_user_id", table_name="audit_logs")
    op.drop_index("ix_audit_logs_tenant_id", table_name="audit_logs")
    op.drop_table("audit_logs")

    op.drop_index("ix_api_keys_status", table_name="api_keys")
    op.drop_index("ix_api_keys_key_prefix", table_name="api_keys")
    op.drop_index("ix_api_keys_tenant_id", table_name="api_keys")
    op.drop_table("api_keys")

    with op.batch_alter_table("agent_tasks") as batch:
        batch.drop_index("ix_agent_tasks_user_id")
        batch.drop_column("user_id")

    with op.batch_alter_table("users") as batch:
        batch.drop_index("ix_users_organization_id")
        batch.drop_constraint("fk_users_organization_id", type_="foreignkey")
        batch.drop_column("organization_id")

    op.drop_index("ix_organizations_org_type", table_name="organizations")
    op.drop_index("ix_organizations_parent_id", table_name="organizations")
    op.drop_index("ix_organizations_tenant_id", table_name="organizations")
    op.drop_table("organizations")

"""add agent runtime tables: agents, agent_tasks, agent_messages, agent_tool_calls, prompt_templates

Revision ID: 0008_agent_runtime
Revises: 0007_add_document_chunks
Create Date: 2026-08-18
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008_agent_runtime"
down_revision: Union[str, None] = "0007_add_document_chunks"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── agents ──
    op.create_table(
        "agents",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("agent_type", sa.String(length=50), nullable=False, server_default="knowledge"),
        sa.Column("config_json", sa.JSON(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agents_tenant_id", "agents", ["tenant_id"])
    op.create_index("ix_agents_agent_type", "agents", ["agent_type"])

    # ── agent_tasks ──
    op.create_table(
        "agent_tasks",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=True),
        sa.Column("agent_id", sa.String(length=36), nullable=True),
        sa.Column("agent_type", sa.String(length=50), nullable=False, server_default="knowledge"),
        sa.Column("input_json", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("result_json", sa.JSON(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], name="fk_agent_tasks_agent_id"),
    )
    op.create_index("ix_agent_tasks_tenant_id", "agent_tasks", ["tenant_id"])
    op.create_index("ix_agent_tasks_agent_id", "agent_tasks", ["agent_id"])
    op.create_index("ix_agent_tasks_status", "agent_tasks", ["status"])

    # ── agent_messages ──
    op.create_table(
        "agent_messages",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=True),
        sa.Column("agent_id", sa.String(length=36), nullable=True),
        sa.Column("task_id", sa.String(length=36), nullable=True),
        sa.Column("conversation_id", sa.String(length=100), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], name="fk_agent_messages_agent_id"),
        sa.ForeignKeyConstraint(["task_id"], ["agent_tasks.id"], name="fk_agent_messages_task_id"),
    )
    op.create_index("ix_agent_messages_tenant_id", "agent_messages", ["tenant_id"])
    op.create_index("ix_agent_messages_agent_id", "agent_messages", ["agent_id"])
    op.create_index("ix_agent_messages_task_id", "agent_messages", ["task_id"])
    op.create_index("ix_agent_messages_conversation_id", "agent_messages", ["conversation_id"])

    # ── agent_tool_calls ──
    op.create_table(
        "agent_tool_calls",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=True),
        sa.Column("task_id", sa.String(length=36), nullable=False),
        sa.Column("tool_name", sa.String(length=100), nullable=False),
        sa.Column("input_json", sa.JSON(), nullable=True),
        sa.Column("output_json", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="success"),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["task_id"], ["agent_tasks.id"], name="fk_agent_tool_calls_task_id"),
    )
    op.create_index("ix_agent_tool_calls_tenant_id", "agent_tool_calls", ["tenant_id"])
    op.create_index("ix_agent_tool_calls_task_id", "agent_tool_calls", ["task_id"])
    op.create_index("ix_agent_tool_calls_tool_name", "agent_tool_calls", ["tool_name"])

    # ── prompt_templates ──
    op.create_table(
        "prompt_templates",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("version", sa.String(length=50), nullable=False, server_default="1.0.0"),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("system_prompt", sa.Text(), nullable=True),
        sa.Column("variables_json", sa.JSON(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("tenant_id", sa.String(length=36), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", "version", name="uq_prompt_templates_name_version"),
    )
    op.create_index("ix_prompt_templates_name", "prompt_templates", ["name"])
    op.create_index("ix_prompt_templates_tenant_id", "prompt_templates", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_prompt_templates_tenant_id", table_name="prompt_templates")
    op.drop_index("ix_prompt_templates_name", table_name="prompt_templates")
    op.drop_table("prompt_templates")

    op.drop_index("ix_agent_tool_calls_tool_name", table_name="agent_tool_calls")
    op.drop_index("ix_agent_tool_calls_task_id", table_name="agent_tool_calls")
    op.drop_index("ix_agent_tool_calls_tenant_id", table_name="agent_tool_calls")
    op.drop_table("agent_tool_calls")

    op.drop_index("ix_agent_messages_conversation_id", table_name="agent_messages")
    op.drop_index("ix_agent_messages_task_id", table_name="agent_messages")
    op.drop_index("ix_agent_messages_agent_id", table_name="agent_messages")
    op.drop_index("ix_agent_messages_tenant_id", table_name="agent_messages")
    op.drop_table("agent_messages")

    op.drop_index("ix_agent_tasks_status", table_name="agent_tasks")
    op.drop_index("ix_agent_tasks_agent_id", table_name="agent_tasks")
    op.drop_index("ix_agent_tasks_tenant_id", table_name="agent_tasks")
    op.drop_table("agent_tasks")

    op.drop_index("ix_agents_agent_type", table_name="agents")
    op.drop_index("ix_agents_tenant_id", table_name="agents")
    op.drop_table("agents")

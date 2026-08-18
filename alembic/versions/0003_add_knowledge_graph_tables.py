"""add knowledge graph tables (entities + relations)

Revision ID: 0003_add_knowledge_graph
Revises: 0002_add_workflow_runs
Create Date: 2026-08-17
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003_add_knowledge_graph"
down_revision: Union[str, None] = "0002_add_workflow_runs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create entity_type enum
    op.execute(
        "CREATE TABLE IF NOT EXISTS entity_type_enum_dummy (dummy INTEGER)"
    )  # placeholder — using native_enum=False in ORM

    op.create_table(
        "knowledge_entities",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=300), nullable=False),
        sa.Column(
            "entity_type",
            sa.String(length=50),
            nullable=False,
            server_default="component",
        ),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
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
    op.create_index("ix_entities_name", "knowledge_entities", ["name"])
    op.create_index("ix_entities_type", "knowledge_entities", ["entity_type"])

    op.create_table(
        "knowledge_relations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_entity_id", sa.Uuid(), nullable=False),
        sa.Column("target_entity_id", sa.Uuid(), nullable=False),
        sa.Column(
            "relation_type",
            sa.String(length=50),
            nullable=False,
            server_default="related_to",
        ),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("source_document_id", sa.String(length=200), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["source_entity_id"],
            ["knowledge_entities.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["target_entity_id"],
            ["knowledge_entities.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_relations_source", "knowledge_relations", ["source_entity_id"]
    )
    op.create_index(
        "ix_relations_target", "knowledge_relations", ["target_entity_id"]
    )
    op.create_index(
        "ix_relations_type", "knowledge_relations", ["relation_type"]
    )


def downgrade() -> None:
    op.drop_index("ix_relations_type", table_name="knowledge_relations")
    op.drop_index("ix_relations_target", table_name="knowledge_relations")
    op.drop_index("ix_relations_source", table_name="knowledge_relations")
    op.drop_table("knowledge_relations")
    op.drop_index("ix_entities_type", table_name="knowledge_entities")
    op.drop_index("ix_entities_name", table_name="knowledge_entities")
    op.drop_table("knowledge_entities")
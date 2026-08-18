"""ORM model creation tests."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.incident.models import IncidentRecord, IncidentStatus
from app.knowledge.models import (
    DocType,
    DocumentStatus,
    KnowledgeCategory,
    KnowledgeDocument,
    KnowledgeTag,
)
from app.sop.models import SOPTemplate


@pytest.mark.asyncio
async def test_create_knowledge_document(db_session: AsyncSession) -> None:
    doc = KnowledgeDocument(
        title="K8s OOM Guide",
        content="# OOM\n\nCheck memory limits.",
        format="markdown",
        doc_type=DocType.SOP,
        status=DocumentStatus.DRAFT,
        source="local",
        author="SRE",
        metadata_json={"env": "prod"},
    )
    db_session.add(doc)
    await db_session.flush()

    assert isinstance(doc.id, uuid.UUID)
    assert doc.doc_type == DocType.SOP
    assert doc.is_active is True


@pytest.mark.asyncio
async def test_category_tree_and_tags(db_session: AsyncSession) -> None:
    root = KnowledgeCategory(name="DevOps", description="root")
    child = KnowledgeCategory(name="Kubernetes", description="k8s", parent=root)
    tag = KnowledgeTag(name="k8s", description="Kubernetes")
    db_session.add_all([root, child, tag])
    await db_session.flush()

    doc = KnowledgeDocument(
        title="Pod Crash",
        content="CrashLoopBackOff",
        doc_type=DocType.INCIDENT,
        category_id=child.id,
    )
    doc.tags.append(tag)
    doc.categories.append(child)
    db_session.add(doc)
    await db_session.flush()

    result = await db_session.execute(
        select(KnowledgeDocument).where(KnowledgeDocument.id == doc.id)
    )
    loaded = result.scalar_one()
    assert loaded.category_id == child.id
    assert child.parent_id == root.id


@pytest.mark.asyncio
async def test_sop_and_incident_models(db_session: AsyncSession) -> None:
    sop = SOPTemplate(
        sop_id="sop-redis-001",
        title="Redis 故障处理",
        severity="P1",
        steps=[{"step": 1, "action": "check process"}],
        rollback=[{"action": "restart"}],
        prerequisites=["access"],
    )
    incident = IncidentRecord(
        title="Redis down",
        service="redis",
        severity="P1",
        status=IncidentStatus.NEW.value,
        root_cause="OOM",
        resolution="restart",
        impact={"users": 100},
        timeline=[{"t": "detect"}],
        related_sop_id="sop-redis-001",
    )
    db_session.add_all([sop, incident])
    await db_session.flush()

    assert sop.sop_id == "sop-redis-001"
    assert incident.status == "new"
    assert incident.solution == "restart"

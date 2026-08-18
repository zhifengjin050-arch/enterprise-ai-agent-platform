"""KnowledgeRepository CRUD tests."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.knowledge.models import DocumentStatus
from app.knowledge.repository import KnowledgeRepository


@pytest.mark.asyncio
async def test_repository_crud(db_session: AsyncSession) -> None:
    repo = KnowledgeRepository(db_session)

    created = await repo.create_document(
        title="Repo Test Doc",
        content="Content body for repository test",
        format="markdown",
        doc_type="SOP",
        source="api",
        author="tester",
        tag_names=["k8s", "docker"],
    )
    await db_session.commit()

    fetched = await repo.get_document(created.id)
    assert fetched is not None
    assert fetched.title == "Repo Test Doc"
    assert {t.name for t in fetched.tags} == {"k8s", "docker"}

    updated = await repo.update_document(
        created.id,
        title="Updated Title",
        status=DocumentStatus.PUBLISHED,
    )
    assert updated is not None
    assert updated.title == "Updated Title"
    assert updated.status == DocumentStatus.PUBLISHED

    docs = await repo.list_documents(status=DocumentStatus.PUBLISHED)
    assert any(d.id == created.id for d in docs)

    deleted = await repo.delete_document(created.id, hard=False)
    assert deleted is True
    archived = await repo.get_document(created.id)
    assert archived is not None
    assert archived.status == DocumentStatus.ARCHIVED

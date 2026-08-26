"""
Knowledge search engine.

Provides full-text search and filtered querying over knowledge documents.
"""

from __future__ import annotations

import uuid
from typing import List, Optional, Union

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.knowledge.models import (
    DocumentStatus,
    KnowledgeDocument,
    document_categories,
    document_tags,
)


class SearchResult:
    """Represents a single search result."""

    def __init__(
        self,
        document: KnowledgeDocument,
        relevance: float = 1.0,
        matched_fields: Optional[List[str]] = None,
    ) -> None:
        self.document = document
        self.relevance = relevance
        self.matched_fields = matched_fields or []


async def search(
    session: AsyncSession,
    query: str,
    doc_type: Optional[str] = None,
    category_id: Optional[Union[str, uuid.UUID]] = None,
    tag_ids: Optional[List[Union[str, uuid.UUID]]] = None,
    source_type: Optional[str] = None,
    active_only: bool = True,
    limit: int = 20,
    offset: int = 0,
) -> List[SearchResult]:
    """Search knowledge documents with optional filters."""
    stmt = select(KnowledgeDocument).distinct()

    if query:
        pattern = f"%{query}%"
        stmt = stmt.where(
            or_(
                KnowledgeDocument.title.ilike(pattern),
                KnowledgeDocument.content.ilike(pattern),
            )
        )

    if doc_type:
        stmt = stmt.where(KnowledgeDocument.doc_type == doc_type)

    if category_id:
        cat_uuid = uuid.UUID(str(category_id))
        stmt = stmt.join(
            document_categories,
            KnowledgeDocument.id == document_categories.c.document_id,
        ).where(document_categories.c.category_id == cat_uuid)

    if tag_ids:
        tag_uuids = [uuid.UUID(str(t)) for t in tag_ids]
        stmt = stmt.join(
            document_tags,
            KnowledgeDocument.id == document_tags.c.document_id,
        ).where(document_tags.c.tag_id.in_(tag_uuids))

    if source_type:
        stmt = stmt.where(KnowledgeDocument.source == source_type)

    if active_only:
        stmt = stmt.where(KnowledgeDocument.status != DocumentStatus.ARCHIVED)

    stmt = stmt.order_by(KnowledgeDocument.updated_at.desc()).limit(limit).offset(offset)
    result = await session.execute(stmt)
    return [SearchResult(doc) for doc in result.scalars().all()]


async def get_document_by_id(
    session: AsyncSession,
    document_id: Union[str, uuid.UUID],
) -> Optional[KnowledgeDocument]:
    """Get a single document by UUID."""
    result = await session.execute(
        select(KnowledgeDocument).where(KnowledgeDocument.id == uuid.UUID(str(document_id)))
    )
    return result.scalar_one_or_none()

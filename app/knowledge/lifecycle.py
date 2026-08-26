"""
Knowledge lifecycle management.

Handles document versioning, expiry detection, and archiving.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import List, Optional, Union

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.knowledge.models import DocumentStatus, KnowledgeDocument

DEFAULT_EXPIRY_PERIODS = {
    "SOP": 180,
    "INCIDENT": 365,
    "BEST_PRACTICE": 180,
    "ARCHITECTURE": 365,
    "CONFIGURATION": 90,
    "OTHER": 365,
    # legacy keys
    "sop": 180,
    "incident": 365,
    "best_practice": 180,
    "architecture": 365,
    "config": 90,
    "general": 365,
}


async def check_expiry(session: AsyncSession) -> List[KnowledgeDocument]:
    """Mark published documents past expires_at as archived."""
    now = datetime.utcnow()
    result = await session.execute(
        select(KnowledgeDocument).where(
            KnowledgeDocument.status != DocumentStatus.ARCHIVED,
            KnowledgeDocument.expires_at.isnot(None),
            KnowledgeDocument.expires_at < now,
        )
    )
    expired = list(result.scalars().all())
    for doc in expired:
        doc.status = DocumentStatus.ARCHIVED
    if expired:
        await session.flush()
    return expired


async def archive_document(
    session: AsyncSession,
    document_id: Union[str, uuid.UUID],
) -> Optional[KnowledgeDocument]:
    """Archive a document (soft delete via status)."""
    result = await session.execute(
        select(KnowledgeDocument).where(KnowledgeDocument.id == uuid.UUID(str(document_id)))
    )
    document = result.scalar_one_or_none()
    if not document:
        return None
    document.status = DocumentStatus.ARCHIVED
    await session.flush()
    await session.refresh(document)
    return document


async def create_new_version(
    session: AsyncSession,
    document_id: Union[str, uuid.UUID],
    new_title: str,
    new_content: str,
) -> Optional[KnowledgeDocument]:
    """Archive current version and create a new incremented version."""
    result = await session.execute(
        select(KnowledgeDocument).where(KnowledgeDocument.id == uuid.UUID(str(document_id)))
    )
    original = result.scalar_one_or_none()
    if not original:
        return None

    original.status = DocumentStatus.ARCHIVED
    new_doc = KnowledgeDocument(
        title=new_title,
        content=new_content,
        format=original.format,
        source=original.source,
        source_url=original.source_url,
        doc_type=original.doc_type,
        status=DocumentStatus.DRAFT,
        version=original.version + 1,
        author=original.author,
        category_id=original.category_id,
        metadata_json=dict(original.metadata_json or {}),
        categories=list(original.categories),
        tags=list(original.tags),
    )
    session.add(new_doc)
    await session.flush()
    await session.refresh(new_doc)
    return new_doc


def calculate_expiry_date(doc_type: str) -> Optional[datetime]:
    """Calculate default expiry date based on document type."""
    days = DEFAULT_EXPIRY_PERIODS.get(doc_type)
    if days is None:
        return None
    return datetime.utcnow() + timedelta(days=days)

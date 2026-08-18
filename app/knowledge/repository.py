"""
Knowledge repository - database access layer.

All knowledge document persistence goes through this repository.
API and workflow layers must not execute raw ORM queries directly.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional, Sequence, Union

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.knowledge.models import (
    DocType,
    DocumentStatus,
    KnowledgeCategory,
    KnowledgeDocument,
    KnowledgeTag,
)


def _as_uuid(value: Union[str, uuid.UUID]) -> uuid.UUID:
    """Normalize string/UUID input to UUID."""
    if isinstance(value, uuid.UUID):
        return value
    return uuid.UUID(str(value))


def _normalize_doc_type(value: Optional[Union[str, DocType]]) -> DocType:
    """Map legacy/lowercase type names to DocType enum."""
    if value is None:
        return DocType.OTHER
    if isinstance(value, DocType):
        return value
    mapping = {
        "sop": DocType.SOP,
        "incident": DocType.INCIDENT,
        "best_practice": DocType.BEST_PRACTICE,
        "architecture": DocType.ARCHITECTURE,
        "config": DocType.CONFIGURATION,
        "configuration": DocType.CONFIGURATION,
        "general": DocType.OTHER,
        "other": DocType.OTHER,
    }
    key = str(value).strip()
    if key in DocType.__members__:
        return DocType[key]
    return mapping.get(key.lower(), DocType.OTHER)


class KnowledgeRepository:
    """Async repository for knowledge documents, categories, and tags."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_document(
        self,
        *,
        title: str,
        content: str,
        format: str = "markdown",
        doc_type: Optional[Union[str, DocType]] = None,
        status: DocumentStatus = DocumentStatus.DRAFT,
        source: str = "local",
        source_url: Optional[str] = None,
        embedding_id: Optional[str] = None,
        quality_score: Optional[float] = None,
        version: int = 1,
        author: Optional[str] = None,
        category_id: Optional[Union[str, uuid.UUID]] = None,
        metadata_json: Optional[Dict[str, Any]] = None,
        tag_names: Optional[Sequence[str]] = None,
        document_id: Optional[Union[str, uuid.UUID]] = None,
    ) -> KnowledgeDocument:
        """Create and persist a knowledge document.

        Args:
            title: Document title.
            content: Markdown body.
            format: Source format (pdf/docx/md/txt/markdown).
            doc_type: Document type enum or legacy string.
            status: Lifecycle status.
            source: Origin identifier.
            source_url: Optional external URL.
            embedding_id: Optional vector store id.
            quality_score: Optional quality score.
            version: Document version number.
            author: Optional author.
            category_id: Optional primary category UUID.
            metadata_json: Optional metadata dict.
            tag_names: Optional tag names to attach.
            document_id: Optional explicit UUID.

        Returns:
            Persisted KnowledgeDocument.
        """
        doc = KnowledgeDocument(
            id=_as_uuid(document_id) if document_id else uuid.uuid4(),
            title=title,
            content=content,
            format=format,
            doc_type=_normalize_doc_type(doc_type),
            status=status,
            source=source,
            source_url=source_url,
            embedding_id=embedding_id,
            quality_score=quality_score,
            version=version,
            author=author,
            category_id=_as_uuid(category_id) if category_id else None,
            metadata_json=metadata_json or {},
        )

        if tag_names:
            for name in tag_names:
                tag = await self.get_or_create_tag(name)
                doc.tags.append(tag)

        self.session.add(doc)
        await self.session.flush()
        await self.session.refresh(doc, attribute_names=["tags", "categories"])
        return doc

    async def get_document(
        self,
        document_id: Union[str, uuid.UUID],
    ) -> Optional[KnowledgeDocument]:
        """Fetch a document by UUID, including tags and categories."""
        stmt = (
            select(KnowledgeDocument)
            .options(
                selectinload(KnowledgeDocument.tags),
                selectinload(KnowledgeDocument.categories),
            )
            .where(KnowledgeDocument.id == _as_uuid(document_id))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_documents(
        self,
        *,
        status: Optional[DocumentStatus] = None,
        doc_type: Optional[Union[str, DocType]] = None,
        tenant_id: Optional[Union[str, uuid.UUID]] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[KnowledgeDocument]:
        """List documents with optional filters (auto tenant when context set)."""
        stmt = select(KnowledgeDocument).options(
            selectinload(KnowledgeDocument.tags),
            selectinload(KnowledgeDocument.categories),
        )
        if status is not None:
            stmt = stmt.where(KnowledgeDocument.status == status)
        if doc_type is not None:
            stmt = stmt.where(KnowledgeDocument.doc_type == _normalize_doc_type(doc_type))
        tid = str(tenant_id) if tenant_id is not None else None
        from app.tenant.context import get_tenant_id as _ctx_tid
        effective = tid or _ctx_tid()
        if effective:
            try:
                stmt = stmt.where(KnowledgeDocument.tenant_id == uuid.UUID(str(effective)))
            except ValueError:
                pass
        stmt = (
            stmt.order_by(KnowledgeDocument.updated_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def update_document(
        self,
        document_id: Union[str, uuid.UUID],
        **fields: Any,
    ) -> Optional[KnowledgeDocument]:
        """Update document fields by UUID.

        Args:
            document_id: Document UUID.
            **fields: Fields to update (title, content, status, etc.).

        Returns:
            Updated document or None if not found.
        """
        doc = await self.get_document(document_id)
        if doc is None:
            return None

        allowed = {
            "title",
            "content",
            "format",
            "doc_type",
            "status",
            "source",
            "source_url",
            "embedding_id",
            "quality_score",
            "version",
            "author",
            "category_id",
            "metadata_json",
            "expires_at",
        }
        for key, value in fields.items():
            if key not in allowed or value is None:
                continue
            if key == "doc_type":
                value = _normalize_doc_type(value)
            if key == "category_id" and value is not None:
                value = _as_uuid(value)
            setattr(doc, key, value)

        await self.session.flush()
        await self.session.refresh(doc)
        return doc

    async def delete_document(
        self,
        document_id: Union[str, uuid.UUID],
        *,
        hard: bool = False,
    ) -> bool:
        """Delete or archive a document.

        Args:
            document_id: Document UUID.
            hard: If True, permanently delete; otherwise archive.

        Returns:
            True if the document existed and was modified/deleted.
        """
        doc = await self.get_document(document_id)
        if doc is None:
            return False
        if hard:
            await self.session.delete(doc)
        else:
            doc.status = DocumentStatus.ARCHIVED
        await self.session.flush()
        return True

    async def update_embedding_id(
        self,
        document_id: Union[str, uuid.UUID],
        embedding_id: Optional[str],
    ) -> Optional[KnowledgeDocument]:
        """Update the embedding_id of a document.

        Args:
            document_id: Document UUID.
            embedding_id: New embedding id (e.g. ``emb_<uuid>_dim1536``).

        Returns:
            Updated document or None if not found.
        """
        return await self.update_document(
            document_id,
            embedding_id=embedding_id,
        )

    async def get_by_embedding_id(
        self,
        embedding_id: str,
    ) -> Optional[KnowledgeDocument]:
        """Look up a document by its embedding_id.

        Args:
            embedding_id: The embedding id to search for.

        Returns:
            The matching document or None.
        """
        stmt = (
            select(KnowledgeDocument)
            .options(
                selectinload(KnowledgeDocument.tags),
                selectinload(KnowledgeDocument.categories),
            )
            .where(KnowledgeDocument.embedding_id == embedding_id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_or_create_tag(self, name: str, description: Optional[str] = None) -> KnowledgeTag:
        """Get an existing tag by name or create it."""
        result = await self.session.execute(
            select(KnowledgeTag).where(KnowledgeTag.name == name)
        )
        tag = result.scalar_one_or_none()
        if tag is not None:
            return tag
        tag = KnowledgeTag(name=name, description=description)
        self.session.add(tag)
        await self.session.flush()
        return tag

    async def get_or_create_category(
        self,
        name: str,
        description: Optional[str] = None,
        parent_id: Optional[Union[str, uuid.UUID]] = None,
    ) -> KnowledgeCategory:
        """Get an existing category by name or create it."""
        result = await self.session.execute(
            select(KnowledgeCategory).where(KnowledgeCategory.name == name)
        )
        category = result.scalar_one_or_none()
        if category is not None:
            return category
        category = KnowledgeCategory(
            name=name,
            description=description,
            parent_id=_as_uuid(parent_id) if parent_id else None,
        )
        self.session.add(category)
        await self.session.flush()
        return category

    async def list_categories(self) -> List[KnowledgeCategory]:
        """List all categories."""
        result = await self.session.execute(
            select(KnowledgeCategory).order_by(KnowledgeCategory.name)
        )
        return list(result.scalars().all())

    async def list_tags(self) -> List[KnowledgeTag]:
        """List all tags."""
        result = await self.session.execute(
            select(KnowledgeTag).order_by(KnowledgeTag.name)
        )
        return list(result.scalars().all())

    @staticmethod
    def to_dict(doc: KnowledgeDocument) -> Dict[str, Any]:
        """Serialize a document to a JSON-friendly dict."""
        return {
            "id": str(doc.id),
            "title": doc.title,
            "content": doc.content,
            "format": doc.format,
            "doc_type": doc.doc_type.value if isinstance(doc.doc_type, DocType) else doc.doc_type,
            "status": doc.status.value if isinstance(doc.status, DocumentStatus) else doc.status,
            "source": doc.source,
            "source_url": doc.source_url,
            "embedding_id": doc.embedding_id,
            "quality_score": doc.quality_score,
            "version": doc.version,
            "author": doc.author,
            "category_id": str(doc.category_id) if doc.category_id else None,
            "metadata_json": doc.metadata_json or {},
            "tags": [t.name for t in (doc.tags or [])],
            "created_at": doc.created_at.isoformat() if doc.created_at else None,
            "updated_at": doc.updated_at.isoformat() if doc.updated_at else None,
            "expires_at": doc.expires_at.isoformat() if doc.expires_at else None,
        }

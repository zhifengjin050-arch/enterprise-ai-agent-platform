"""Search index manager.

Handles creation, updating, and rebuilding of search indices
for both full-text (FTS5/PostgreSQL FTS) and semantic (ChromaDB)
search backends.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

from app.core.config import get_settings
from app.db.session import get_session_factory
from app.embedding.client import OpenAICompatibleEmbedding
from app.knowledge.models import DocumentStatus, KnowledgeDocument
from app.knowledge.repository import KnowledgeRepository
from app.vectorstore.chroma_store import ChromaStore


class KnowledgeIndexer:
    """Manages search index lifecycle for both full-text and vector backends.

    Provides operations for indexing individual documents, rebuilding
    indices, and syncing missing embeddings.
    """

    def __init__(
        self,
        embedding_provider: Optional[OpenAICompatibleEmbedding] = None,
        vector_store: Optional[ChromaStore] = None,
    ) -> None:
        self._settings = get_settings()
        self._embedding = embedding_provider or OpenAICompatibleEmbedding()
        self._store = vector_store or ChromaStore()

    async def index_document(
        self,
        document_id: str,
        *,
        embedding_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Index a single document in ChromaDB.

        Fetches the document from the database, generates its embedding
        if not already present, and upserts the vector into ChromaDB.

        Args:
            document_id: Document UUID.
            embedding_id: Optional pre-existing embedding id. If None,
                          the method will generate one.

        Returns:
            Dict with status info: ``{"indexed": bool, "embedding_id": str}``.
        """
        factory = get_session_factory()
        async with factory() as session:
            repo = KnowledgeRepository(session)
            doc = await repo.get_document(document_id)

            if doc is None:
                return {"indexed": False, "error": "Document not found"}

            # Determine or generate embedding_id
            eid = embedding_id or doc.embedding_id
            if not eid:
                eid = f"emb_{uuid.uuid4().hex[:12]}"
                doc.embedding_id = eid
                await session.flush()

            # Get or compute the embedding vector
            vector: Optional[List[float]] = None
            if doc.embedding_id and doc.embedding_id.startswith("emb_"):
                # Generate embedding from content
                embed_text = f"{doc.title or ''}\\n\\n{(doc.content or '')[:4096]}"
                if embed_text.strip():
                    vector = await self._embedding.embed_text(embed_text)

            if vector is None:
                # Fallback: zero vector with configured dimension
                vector = [0.0] * (self._settings.embedding_dimension or 1536)

            # Build metadata for ChromaDB
            metadata: Dict[str, Any] = {
                "document_id": str(doc.id),
                "title": doc.title or "",
                "doc_type": doc.doc_type.value if doc.doc_type else "",
                "category": "",
                "tags": [t.name for t in (doc.tags or [])],
                "source": doc.source or "",
            }

            # Upsert into ChromaDB
            try:
                exists = await self._store.count() > 0
                if exists:
                    await self._store.update(
                        document_id=eid,
                        embedding=vector,
                        metadata=metadata,
                        content=(doc.content or "")[:500],
                    )
                else:
                    await self._store.add(
                        document_id=eid,
                        embedding=vector,
                        metadata=metadata,
                        content=(doc.content or "")[:500],
                    )
            except Exception as exc:
                logger.warning("ChromaDB update failed, falling back to add: %s", exc)
                await self._store.add(
                    document_id=eid,
                    embedding=vector,
                    metadata=metadata,
                    content=(doc.content or "")[:500],
                )

            await session.commit()
            return {"indexed": True, "embedding_id": eid}

    async def index_chunks(
        self,
        document_id: str,
        chunks: List[Any],
        vectors: Optional[List[List[float]]] = None,
    ) -> Dict[str, Any]:
        """Index document chunks into ChromaDB at chunk granularity.

        Args:
            document_id: Parent document UUID.
            chunks: Chunk-like objects with id/content/heading attributes.
            vectors: Optional precomputed embeddings aligned with chunks.

        Returns:
            Dict with indexed count.
        """
        if not chunks:
            return {"indexed": 0}

        if vectors is None:
            texts = [getattr(c, "content", "") or "" for c in chunks]
            vectors = await self._embedding.embed_documents(texts)

        indexed = 0
        for i, chunk in enumerate(chunks):
            chunk_id = str(getattr(chunk, "id", f"{document_id}:{i}"))
            content = getattr(chunk, "content", "") or ""
            heading = getattr(chunk, "heading", "") or ""
            vector = (
                vectors[i]
                if i < len(vectors)
                else [0.0] * (get_settings().embedding_dimension or 1536)
            )
            metadata: Dict[str, Any] = {
                "document_id": str(document_id),
                "chunk_id": chunk_id,
                "chunk_index": getattr(chunk, "chunk_index", i),
                "title": heading,
                "source": "chunk",
            }
            chunk_meta = getattr(chunk, "metadata", None) or {}
            from app.security.acl import DocumentACL

            metadata.update(DocumentACL.from_metadata(chunk_meta).chroma_fields())
            eid = f"chunk_{chunk_id[:24]}"
            try:
                await self._store.add(
                    document_id=eid,
                    embedding=vector,
                    metadata=metadata,
                    content=content[:500],
                )
                indexed += 1
            except Exception as exc:
                logger.warning("Chunk index failed for %s: %s", chunk_id, exc)

        return {"indexed": indexed, "document_id": document_id}

    async def delete_document(self, embedding_id: str) -> None:
        """Remove a document from the vector index.

        Args:
            embedding_id: The embedding identifier used as ChromaDB id.
        """
        await self._store.delete(embedding_id)

    async def rebuild_index(self) -> Dict[str, Any]:
        """Full rebuild of the vector search index.

        Iterates all active documents, generates embeddings, and
        populates ChromaDB. This is a batch operation.

        Returns:
            Dict with ``{"indexed": int, "failed": int, "total": int}``.
        """
        factory = get_session_factory()
        async with factory() as session:
            result = await session.execute(
                KnowledgeDocument.__table__.select().where(
                    KnowledgeDocument.status == DocumentStatus.ACTIVE
                )
            )
            rows = result.fetchall()

        indexed = 0
        failed = 0
        for row in rows:
            try:
                r = await self.index_document(str(row[0]))
                if r.get("indexed"):
                    indexed += 1
                else:
                    failed += 1
            except Exception:
                failed += 1

        return {"indexed": indexed, "failed": failed, "total": len(rows)}

    async def sync_missing_embeddings(self) -> Dict[str, Any]:
        """Find documents without ChromaDB vectors and index them.

        Returns:
            Dict with ``{"synced": int, "skipped": int}``.
        """
        factory = get_session_factory()
        async with factory() as session:
            result = await session.execute(
                KnowledgeDocument.__table__.select().where(
                    KnowledgeDocument.status == DocumentStatus.ACTIVE,
                    KnowledgeDocument.embedding_id.isnot(None),
                )
            )
            rows = result.fetchall()

        synced = 0
        for row in rows:
            eid = str(row[0])  # fallback
            # Find embedding_id column
            embedding_id = getattr(row, "embedding_id", None) or eid
            try:
                r = await self.index_document(str(row[0]), embedding_id=embedding_id)
                if r.get("indexed"):
                    synced += 1
            except Exception as exc:
                logger.warning("Index sync failed for doc: %s", exc)

        return {"synced": synced, "skipped": len(rows) - synced}

    async def get_index_stats(self) -> Dict[str, Any]:
        """Get statistics about the current vector search index.

        Returns:
            Dict with keys: total_docs, vector_indexed.
        """
        try:
            vector_count = await self._store.count()
        except Exception as exc:
            logger.warning("Failed to get index stats: %s", exc)
            vector_count = 0

        return {
            "vector_indexed": vector_count,
        }

    async def close(self) -> None:
        """Release underlying HTTP and ChromaDB resources."""
        await self._embedding.close()


# Module-level convenience instance
_indexer: Optional[KnowledgeIndexer] = None


def get_indexer() -> KnowledgeIndexer:
    """Return a singleton KnowledgeIndexer instance."""
    global _indexer
    if _indexer is None:
        _indexer = KnowledgeIndexer()
    return _indexer

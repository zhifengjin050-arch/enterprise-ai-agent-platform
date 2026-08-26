"""Repository for DocumentChunk persistence."""

from __future__ import annotations

from typing import List, Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.knowledge.chunk_models import DocumentChunk
from app.knowledge.chunking import Chunk


class DocumentChunkRepository:
    """CRUD for document_chunks table."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save_chunks(
        self,
        chunks: List[Chunk],
        *,
        embedding_ids: Optional[List[Optional[str]]] = None,
    ) -> List[DocumentChunk]:
        """Persist a list of in-memory Chunks.

        Args:
            chunks: Chunks from SmartChunker.
            embedding_ids: Optional parallel list of vector store IDs.

        Returns:
            Persisted DocumentChunk rows.
        """
        records: List[DocumentChunk] = []
        for i, chunk in enumerate(chunks):
            emb_id = None
            if embedding_ids and i < len(embedding_ids):
                emb_id = embedding_ids[i]
            record = DocumentChunk(
                id=chunk.id,
                document_id=chunk.document_id,
                chunk_index=chunk.chunk_index,
                content=chunk.content,
                heading=chunk.heading,
                token_count=chunk.token_count,
                embedding_id=emb_id,
                metadata_json=chunk.metadata or {},
            )
            self._session.add(record)
            records.append(record)
        await self._session.flush()
        for r in records:
            await self._session.refresh(r)
        return records

    async def list_by_document(self, document_id: str, *, limit: int = 500) -> List[DocumentChunk]:
        """List chunks for a document ordered by chunk_index."""
        stmt = (
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.chunk_index.asc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def delete_by_document(self, document_id: str) -> int:
        """Delete all chunks for a document. Returns count deleted."""
        existing = await self.list_by_document(document_id)
        count = len(existing)
        if count:
            stmt = delete(DocumentChunk).where(DocumentChunk.document_id == document_id)
            await self._session.execute(stmt)
            await self._session.flush()
        return count

    async def get(self, chunk_id: str) -> Optional[DocumentChunk]:
        """Get a chunk by ID."""
        stmt = select(DocumentChunk).where(DocumentChunk.id == chunk_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

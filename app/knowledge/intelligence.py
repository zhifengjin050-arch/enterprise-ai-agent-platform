"""Intelligence pipeline helpers — chunk + index a stored document.

Called from DocumentPipeline / workflow after a document is stored,
or invoked directly by APIs / SyncEvent consumers.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.knowledge.chunk_repository import DocumentChunkRepository
from app.knowledge.chunking import SmartChunker
from app.knowledge.embedding import ChunkEmbeddingService
from app.knowledge.graph import KnowledgeGraph

logger = logging.getLogger(__name__)


async def process_document_intelligence(
    session: AsyncSession,
    *,
    document_id: str,
    title: str,
    content: str,
    embed: bool = True,
    build_graph: bool = True,
    max_tokens: int = 512,
) -> Dict[str, Any]:
    """Run Intelligence Layer processing on a document.

    Steps:
        1. SmartChunker → chunks
        2. Persist DocumentChunk rows (replace existing)
        3. Optional: embed chunks
        4. Optional: build knowledge graph

    Args:
        session: DB session.
        document_id: Knowledge document ID.
        title: Document title.
        content: Markdown content.
        embed: Whether to embed chunks.
        build_graph: Whether to extract entities/relations.
        max_tokens: Chunk token budget.

    Returns:
        Summary dict with chunk_count, entity_count, relation_count.
    """
    chunker = SmartChunker(max_tokens=max_tokens)
    chunks = chunker.chunk(content, document_id=document_id, title=title)

    repo = DocumentChunkRepository(session)
    await repo.delete_by_document(document_id)

    embedding_ids: Optional[List[Optional[str]]] = None
    vectors: Optional[List[List[float]]] = None
    if embed and chunks:
        try:
            service = ChunkEmbeddingService()
            vectors = await service.embed_chunks(chunks)
            embedding_ids = [c.id for c in chunks]
            # Phase 5 follow-up: chunk-level Chroma index
            try:
                from app.search.indexer import KnowledgeIndexer

                indexer = KnowledgeIndexer()
                await indexer.index_chunks(document_id, chunks, vectors=vectors)
            except Exception as idx_exc:
                logger.warning("Chunk Chroma index skipped: %s", idx_exc)
            logger.info(
                "Embedded %d chunks for document %s (dim=%s)",
                len(vectors),
                document_id,
                len(vectors[0]) if vectors else 0,
            )
        except Exception as exc:
            logger.warning(
                "Chunk embedding skipped for %s: %s", document_id, exc
            )
            embedding_ids = None
            vectors = None

    records = await repo.save_chunks(chunks, embedding_ids=embedding_ids)

    entity_count = 0
    relation_count = 0
    if build_graph:
        try:
            kg = KnowledgeGraph(session)
            result = await kg.build_from_document(
                title=title,
                content=content,
                document_id=document_id,
                session=session,
            )
            entity_count = len(result.get("entities") or [])
            relation_count = len(result.get("relations") or [])
        except Exception as exc:
            logger.warning(
                "Graph build skipped for %s: %s", document_id, exc
            )

    await session.flush()
    logger.info(
        "Intelligence processed document %s: chunks=%d entities=%d relations=%d",
        document_id,
        len(records),
        entity_count,
        relation_count,
    )
    return {
        "document_id": document_id,
        "chunk_count": len(records),
        "entity_count": entity_count,
        "relation_count": relation_count,
    }

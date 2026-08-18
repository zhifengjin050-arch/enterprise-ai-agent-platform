"""Unified KnowledgeRetriever for the Intelligence Layer.

Combines:
    Vector Search + BM25/FTS + Knowledge Graph → Rerank → TopN

Returns RetrievalResult with document_id, chunk_id, score, source, metadata.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.knowledge.hybrid_search import IntelligenceHybridSearch
from app.knowledge.reranker import Reranker

logger = logging.getLogger(__name__)


@dataclass
class RetrievalResult:
    """Unified retrieval result from the Knowledge Intelligence Layer.

    Attributes:
        document_id: Parent knowledge document ID.
        chunk_id: Chunk ID (empty for document-level hits).
        score: Relevance score (post-rerank when applicable).
        source: Origin channel (hybrid / vector / bm25 / graph).
        metadata: Extra metadata (title, content snippet, entities, etc.).
        content: Snippet / chunk content for convenience.
        title: Document or section title.
    """

    document_id: str
    chunk_id: str = ""
    score: float = 0.0
    source: str = "hybrid"
    metadata: Dict[str, Any] = field(default_factory=dict)
    content: str = ""
    title: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "document_id": self.document_id,
            "chunk_id": self.chunk_id,
            "score": self.score,
            "source": self.source,
            "metadata": self.metadata,
            "content": self.content,
            "title": self.title,
        }


class KnowledgeRetriever:
    """Enterprise knowledge retriever: hybrid recall → rerank → TopN.

    Args:
        hybrid: Optional IntelligenceHybridSearch override.
        reranker: Optional Reranker override.
        recall_k: TopK for initial recall (default 20).
        top_n: TopN after reranking (default 5).
    """

    def __init__(
        self,
        hybrid: Optional[IntelligenceHybridSearch] = None,
        reranker: Optional[Reranker] = None,
        recall_k: int = 20,
        top_n: int = 5,
    ) -> None:
        self._hybrid = hybrid or IntelligenceHybridSearch()
        self._reranker = reranker or Reranker()
        self.recall_k = recall_k
        self.top_n = top_n

    async def retrieve(
        self,
        query: str,
        *,
        top_n: Optional[int] = None,
        recall_k: Optional[int] = None,
        filters: Optional[Dict[str, Any]] = None,
        use_graph: bool = True,
        use_rerank: bool = True,
        session: Any = None,
    ) -> List[RetrievalResult]:
        """Retrieve relevant knowledge for a query.

        Args:
            query: User query.
            top_n: Override TopN after rerank.
            recall_k: Override TopK recall.
            filters: Optional metadata filters.
            use_graph: Enable graph entity boost.
            use_rerank: Enable reranking step.
            session: Optional DB session for graph lookup.

        Returns:
            List of RetrievalResult ordered by score descending.
        """
        k = recall_k or self.recall_k
        n = top_n or self.top_n

        hybrid_results = await self._hybrid.search(
            query,
            top_k=k,
            filters=filters,
            use_graph=use_graph,
            session=session,
        )

        candidates = [
            RetrievalResult(
                document_id=r.document_id,
                chunk_id=r.chunk_id,
                score=r.score,
                source=r.source,
                metadata=r.metadata,
                content=r.content,
                title=r.title,
            )
            for r in hybrid_results
        ]

        if use_rerank and candidates:
            candidates = self._reranker.rerank(
                query,
                candidates,
                top_n=n,
                text_field="content",
                score_field="score",
            )
        else:
            candidates = candidates[:n]

        logger.info(
            "KnowledgeRetriever: query=%r recall=%d → top_n=%d",
            query[:80],
            len(hybrid_results),
            len(candidates),
        )
        return candidates

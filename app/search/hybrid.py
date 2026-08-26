"""Hybrid search engine.

Combines full-text and semantic search results using Reciprocal Rank
Fusion (RRF) to produce a single, relevance-ranked result set.

RRF formula:
    score(d) = Σ 1 / (k + rank_i(d))

where rank_i(d) is the rank of document d in search mode i,
and k is a constant (default 60).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.search.fulltext import FullTextSearch, get_fulltext_search
from app.search.semantic import SemanticSearch, get_semantic_search


@dataclass
class HybridResult:
    """A single hybrid search result with combined scoring."""

    id: str
    title: str
    snippet: str
    score: float
    metadata: Dict[str, Any] = field(default_factory=dict)


def rrf_score(rank: int, k: int = 60) -> float:
    """Calculate the RRF contribution for a document at a given rank.

    Args:
        rank: 1-based rank position.
        k: RRF constant (default 60).

    Returns:
        RRF score contribution: 1 / (k + rank).
    """
    return 1.0 / (k + rank)


class HybridSearch:
    """Hybrid search combining full-text and semantic via RRF.

    Executes both searches in parallel (conceptually), then fuses
    results using Reciprocal Rank Fusion for a unified ranking.
    """

    def __init__(
        self,
        fulltext: Optional[FullTextSearch] = None,
        semantic: Optional[SemanticSearch] = None,
        rrf_k: int = 60,
    ) -> None:
        self._fulltext = fulltext or get_fulltext_search()
        self._semantic = semantic or get_semantic_search()
        self._rrf_k = rrf_k

    async def search(
        self,
        query: str,
        top_k: int = 20,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[HybridResult]:
        """Execute hybrid search with RRF fusion.

        Args:
            query: Search query string.
            top_k: Maximum number of results.
            filters: Optional metadata filters.

        Returns:
            List of HybridResult ordered by combined RRF score (desc).
        """
        # Run both searches concurrently
        ft_results = await self._fulltext.search(
            query=query,
            filters=filters,
            limit=top_k * 2,
            offset=0,
        )
        sem_results = await self._semantic.search(
            query=query,
            top_k=top_k * 2,
            filters=filters,
        )

        # Build RRF score map
        rrf_scores: Dict[str, float] = {}
        result_map: Dict[str, HybridResult] = {}

        # Full-text ranks (1-based)
        for rank, ft in enumerate(ft_results, start=1):
            score = rrf_score(rank, self._rrf_k)
            rrf_scores[ft.id] = rrf_scores.get(ft.id, 0.0) + score
            result_map[ft.id] = HybridResult(
                id=ft.id,
                title=ft.title,
                snippet=ft.snippet,
                score=0.0,  # will be updated
                metadata=ft.metadata,
            )

        # Semantic ranks (1-based)
        for rank, sem in enumerate(sem_results, start=1):
            score = rrf_score(rank, self._rrf_k)
            rrf_scores[sem.id] = rrf_scores.get(sem.id, 0.0) + score
            if sem.id not in result_map:
                result_map[sem.id] = HybridResult(
                    id=sem.id,
                    title=sem.title,
                    snippet=sem.content[:200] if sem.content else "",
                    score=0.0,
                    metadata=sem.metadata,
                )

        # Assign final scores
        for doc_id in result_map:
            result_map[doc_id].score = rrf_scores.get(doc_id, 0.0)

        # Sort by score descending, take top_k
        sorted_results = sorted(
            result_map.values(),
            key=lambda r: r.score,
            reverse=True,
        )
        return sorted_results[:top_k]


# Module-level convenience instance
_hybrid: Optional[HybridSearch] = None


def get_hybrid_search() -> HybridSearch:
    """Return a singleton HybridSearch instance."""
    global _hybrid
    if _hybrid is None:
        _hybrid = HybridSearch()
    return _hybrid

"""Hybrid search for the Knowledge Intelligence Layer.

Wraps app.search.hybrid.HybridSearch and optionally boosts results
using Knowledge Graph entity matches.

Imports from app.search are deferred to avoid circular imports with
app.knowledge.models (search.fulltext → knowledge.models).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class IntelligenceHybridResult:
    """Hybrid search result with intelligence-layer fields."""

    document_id: str
    chunk_id: str = ""
    score: float = 0.0
    source: str = "hybrid"
    title: str = ""
    content: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "document_id": self.document_id,
            "chunk_id": self.chunk_id,
            "score": self.score,
            "source": self.source,
            "title": self.title,
            "content": self.content,
            "metadata": self.metadata,
        }


class IntelligenceHybridSearch:
    """Vector + BM25/FTS hybrid search with optional graph boost.

    Args:
        hybrid: Optional HybridSearch override.
        graph_boost: Score boost when query matches a known entity (default 0.1).
    """

    def __init__(
        self,
        hybrid: Optional[Any] = None,
        graph_boost: float = 0.1,
    ) -> None:
        self._hybrid = hybrid
        self._graph_boost = graph_boost

    def _get_hybrid(self) -> Any:
        if self._hybrid is not None:
            return self._hybrid
        from app.search.hybrid import get_hybrid_search

        return get_hybrid_search()

    async def search(
        self,
        query: str,
        *,
        top_k: int = 20,
        filters: Optional[Dict[str, Any]] = None,
        use_graph: bool = True,
        session: Any = None,
    ) -> List[IntelligenceHybridResult]:
        """Execute hybrid search and optionally apply graph boost."""
        hybrid = self._get_hybrid()
        raw = await hybrid.search(query=query, top_k=top_k, filters=filters)

        entity_names: set[str] = set()
        if use_graph and session is not None:
            entity_names = await self._lookup_entities(query, session)

        results: List[IntelligenceHybridResult] = []
        for item in raw:
            score = item.score
            meta = dict(item.metadata or {})
            if entity_names:
                text_blob = f"{item.title} {item.snippet}".lower()
                hits = [e for e in entity_names if e.lower() in text_blob]
                if hits:
                    score += self._graph_boost * len(hits)
                    meta["graph_entities"] = hits

            results.append(
                IntelligenceHybridResult(
                    document_id=item.id,
                    chunk_id=meta.get("chunk_id", ""),
                    score=score,
                    source="hybrid",
                    title=item.title,
                    content=item.snippet,
                    metadata=meta,
                )
            )

        results.sort(key=lambda r: r.score, reverse=True)
        return results[:top_k]

    async def _lookup_entities(self, query: str, session: Any) -> set[str]:
        """Find entity names that appear in the query."""
        try:
            from app.entity.repository import EntityRepository

            repo = EntityRepository(session)
            entities = await repo.list_entities(limit=200)
            names = {e.name for e in entities if e.name}
            q_lower = query.lower()
            return {n for n in names if n.lower() in q_lower}
        except Exception as exc:
            logger.warning("Graph entity lookup failed: %s", exc)
            return set()


# Alias for Phase 5 naming
KnowledgeHybridSearch = IntelligenceHybridSearch

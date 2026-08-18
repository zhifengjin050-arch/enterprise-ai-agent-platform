"""Reranker for Knowledge Intelligence retrieval.

Pipeline:
    TopK recall → Rerank → TopN results

Provides a lightweight lexical/semantic hybrid score reranker that does
not require an external cross-encoder model (works offline).  When an
optional scorer callable is injected, it is used instead.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Callable, List, Optional, Sequence

logger = logging.getLogger(__name__)

# Type for optional external score function: (query, text) -> float
ScoreFn = Callable[[str, str], float]


def _tokenize(text: str) -> set[str]:
    """Simple alphanumeric / CJK tokenisation."""
    tokens = re.findall(r"[\w\u4e00-\u9fff]+", text.lower())
    return set(tokens)


def _lexical_overlap(query: str, text: str) -> float:
    """Jaccard overlap between query and text tokens."""
    q = _tokenize(query)
    t = _tokenize(text)
    if not q or not t:
        return 0.0
    return len(q & t) / len(q | t)


class Reranker:
    """Rerank retrieval candidates and return TopN.

    Combines the original retrieval score with lexical overlap to
    produce a final ranking.  Supports an optional external score_fn
    for plugging in a cross-encoder later.

    Args:
        score_fn: Optional (query, text) → float external scorer.
        lexical_weight: Weight for lexical overlap (default 0.3).
        original_weight: Weight for original retrieval score (default 0.7).
    """

    def __init__(
        self,
        score_fn: Optional[ScoreFn] = None,
        lexical_weight: float = 0.3,
        original_weight: float = 0.7,
    ) -> None:
        self._score_fn = score_fn
        self._lexical_weight = lexical_weight
        self._original_weight = original_weight

    def rerank(
        self,
        query: str,
        results: Sequence[Any],
        *,
        top_n: int = 5,
        text_field: str = "content",
        score_field: str = "score",
    ) -> List[Any]:
        """Rerank results and return the top N.

        Args:
            query: Original user query.
            results: Candidates from TopK recall (RetrievalResult or similar).
            top_n: Number of results to keep after reranking.
            text_field: Attribute/key for text content.
            score_field: Attribute/key for original score.

        Returns:
            Top N results sorted by rerank score descending.
            Mutates ``score`` on objects that have that attribute.
        """
        if not results:
            return []

        scored: List[tuple[float, Any]] = []
        for item in results:
            text = self._get_field(item, text_field) or self._get_field(item, "snippet") or ""
            original = float(self._get_field(item, score_field) or 0.0)

            if self._score_fn is not None:
                rerank_score = self._score_fn(query, str(text))
            else:
                lexical = _lexical_overlap(query, str(text))
                # Normalise original score roughly into [0, 1]
                norm_original = min(1.0, max(0.0, original))
                if original > 1.0:
                    norm_original = min(1.0, original / (original + 1.0))
                rerank_score = (
                    self._original_weight * norm_original
                    + self._lexical_weight * lexical
                )

            # Write back score if possible
            if hasattr(item, score_field):
                setattr(item, score_field, rerank_score)
            elif isinstance(item, dict):
                item[score_field] = rerank_score

            scored.append((rerank_score, item))

        scored.sort(key=lambda x: x[0], reverse=True)
        top = [item for _, item in scored[:top_n]]
        logger.info(
            "Reranked %d candidates → top %d",
            len(results),
            len(top),
        )
        return top

    @staticmethod
    def _get_field(item: Any, field: str) -> Any:
        if isinstance(item, dict):
            return item.get(field)
        return getattr(item, field, None)

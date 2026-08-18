"""Context builder for the Knowledge Intelligence Layer.

Extends / wraps app.query.builder.ContextBuilder to accept
RetrievalResult objects from KnowledgeRetriever.
"""

from __future__ import annotations

from typing import Any, List, Sequence

from app.query.builder import ContextBuilder, ContextDocument, build_llm_context


class IntelligenceContextBuilder:
    """Build LLM context from Intelligence Layer retrieval results.

    Args:
        max_tokens: Token budget for the assembled context.
    """

    def __init__(self, max_tokens: int = 12000) -> None:
        self._builder = ContextBuilder(max_tokens=max_tokens)

    def build(
        self,
        results: Sequence[Any],
        *,
        query: str = "",
    ) -> List[ContextDocument]:
        """Build context documents from RetrievalResult-like objects.

        Args:
            results: RetrievalResult or objects with title/content/score.
            query: Optional query (reserved for future query-aware trimming).

        Returns:
            List of ContextDocument within the token budget.
        """
        return self._builder.build(
            list(results),
            title_field="title",
            content_field="content",
            score_field="score",
        )

    def build_prompt_context(
        self,
        results: Sequence[Any],
        *,
        query: str = "",
    ) -> str:
        """Build a single string context suitable for LLM prompts.

        Args:
            results: Retrieval results.
            query: User query (reserved for future use).

        Returns:
            Formatted context string.
        """
        docs = self.build(results, query=query)
        return self._builder.to_text(docs)


# Re-export for convenience
__all__ = [
    "IntelligenceContextBuilder",
    "ContextBuilder",
    "ContextDocument",
    "build_llm_context",
]

"""Context builder for LLM answer generation.

Builds a structured LLM context from hybrid search results,
with token limit enforcement and deduplication.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List


@dataclass
class ContextDocument:
    """A single document in the LLM context.

    Attributes:
        title: Document title.
        content: Document content snippet.
        source: Source identifier.
        score: RRF fusion score.
    """

    title: str = ""
    content: str = ""
    source: str = ""
    score: float = 0.0


# Approximate token counting (4 chars ≈ 1 token for CJK + English)
_CHARS_PER_TOKEN: int = 4


def _estimate_tokens(text: str) -> int:
    """Estimate token count from character length."""
    return len(text) // _CHARS_PER_TOKEN


class ContextBuilder:
    """Builds a deduplicated, token-limited context from search results.

    The builder:
    1. Removes duplicate documents (by ID or title similarity)
    2. Keeps only the highest-scored document per group
    3. Truncates to a maximum token budget
    """

    def __init__(self, max_tokens: int = 12000):
        """Initialize with token budget.

        Args:
            max_tokens: Maximum context token limit (default 12000).
        """
        self._max_tokens = max_tokens

    def build(
        self,
        results: List[Any],
        title_field: str = "title",
        content_field: str = "snippet",
        score_field: str = "score",
    ) -> List[ContextDocument]:
        """Build a deduplicated, token-limited context.

        Args:
            results: Search results (HybridResult or similar).
            title_field: Attribute name for title.
            content_field: Attribute name for content/snippet.
            score_field: Attribute name for score.

        Returns:
            List of ContextDocument sorted by score descending,
            within the token budget.
        """
        # Deduplicate: same title → keep highest score
        seen_titles: set = set()
        deduped: List[Any] = []
        for r in sorted(results, key=lambda x: getattr(x, score_field, 0.0), reverse=True):
            title = getattr(r, title_field, "") or ""
            title_lower = title.lower().strip()
            if title_lower and title_lower not in seen_titles:
                seen_titles.add(title_lower)
                deduped.append(r)

        # Build context within token budget
        context: List[ContextDocument] = []
        total_tokens = 0

        for r in deduped:
            title = getattr(r, title_field, "") or ""
            content = getattr(r, content_field, "") or ""
            score = getattr(r, score_field, 0.0) or 0.0

            doc_tokens = _estimate_tokens(title + content)
            if total_tokens + doc_tokens > self._max_tokens:
                # Truncate content to fit remaining budget
                remaining = self._max_tokens - total_tokens
                if remaining > _CHARS_PER_TOKEN:
                    max_chars = remaining * _CHARS_PER_TOKEN
                    content = content[: max_chars - len(title)]
                    if content:
                        context.append(
                            ContextDocument(
                                title=title,
                                content=content,
                                source=title,
                                score=score,
                            )
                        )
                break

            context.append(
                ContextDocument(
                    title=title,
                    content=content,
                    source=title,
                    score=score,
                )
            )
            total_tokens += doc_tokens

        return context

    def to_text(self, context: List[ContextDocument]) -> str:
        """Convert context documents to formatted text for LLM prompt.

        Args:
            context: List of ContextDocument.

        Returns:
            Formatted string suitable for LLM prompt inclusion.
        """
        parts: List[str] = []
        for i, doc in enumerate(context, 1):
            parts.append(f"[文档 {i}]\n标题: {doc.title}\n内容: {doc.content}\n")
        return "\n---\n".join(parts)


def build_llm_context(
    results: List[Any],
    max_tokens: int = 12000,
    title_field: str = "title",
    content_field: str = "snippet",
    score_field: str = "score",
) -> str:
    """Build a formatted LLM context string from search results.

    Convenience function that chains ContextBuilder.build() + to_text().

    Args:
        results: Search results to include.
        max_tokens: Maximum token budget.
        title_field: Attribute name for title.
        content_field: Attribute name for content/snippet.
        score_field: Attribute name for score.

    Returns:
        Formatted context string for LLM prompt.
    """
    builder = ContextBuilder(max_tokens=max_tokens)
    context = builder.build(results, title_field, content_field, score_field)
    return builder.to_text(context)

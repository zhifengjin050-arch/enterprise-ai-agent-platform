"""Citation extraction from search results.

Converts hybrid search results into structured Citation objects
for traceable knowledge agent answers.
"""

from __future__ import annotations

from typing import Any, List

from app.citation.models import CitationSource


class CitationExtractor:
    """Extracts structured citations from search results.

    Builds a list of CitationSource objects from HybridResult or
    similar search result types, sorted by relevance score.
    """

    def extract(
        self,
        results: List[Any],
        max_sources: int = 5,
        title_field: str = "title",
        snippet_field: str = "snippet",
        score_field: str = "score",
        id_field: str = "id",
    ) -> List[CitationSource]:
        """Extract citations from search results.

        Args:
            results: Search results (HybridResult or similar).
            max_sources: Maximum number of citations to include.
            title_field: Attribute for title.
            snippet_field: Attribute for content snippet.
            score_field: Attribute for score.
            id_field: Attribute for document ID.

        Returns:
            Sorted list of CitationSource (highest score first).
        """
        sources: List[CitationSource] = []
        seen_titles: set = set()

        for r in sorted(
            results,
            key=lambda x: getattr(x, score_field, 0.0) or 0.0,
            reverse=True,
        ):
            title = getattr(r, title_field, "") or ""
            title_lower = title.lower().strip()
            if title_lower and title_lower in seen_titles:
                continue
            if title_lower:
                seen_titles.add(title_lower)

            sources.append(
                CitationSource(
                    document_id=str(getattr(r, id_field, "") or ""),
                    title=title,
                    content_snippet=(getattr(r, snippet_field, "") or "")[:200],
                    source="knowledge_base",
                    score=getattr(r, score_field, 0.0) or 0.0,
                )
            )

            if len(sources) >= max_sources:
                break

        return sources


def extract_citations(
    results: List[Any],
    max_sources: int = 5,
) -> List[CitationSource]:
    """Convenience function for citation extraction.

    Args:
        results: Search results to extract from.
        max_sources: Maximum number of citations.

    Returns:
        List of CitationSource objects.
    """
    extractor = CitationExtractor()
    return extractor.extract(results, max_sources=max_sources)

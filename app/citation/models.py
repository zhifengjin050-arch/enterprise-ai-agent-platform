"""Citation data models.

Represents a traceable reference from a knowledge document
that supports an agent's answer.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class CitationSource:
    """Source document metadata for a citation.

    Attributes:
        document_id: Unique document identifier.
        title: Document title.
        content_snippet: Short excerpt from the source.
        source: Source system identifier (e.g., "knowledge_base", "wiki").
        page: Optional page number or section reference.
        score: Relevance score from search ranking.
    """
    document_id: str = ""
    title: str = ""
    content_snippet: str = ""
    source: str = "knowledge_base"
    page: Optional[int] = None
    score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to a serializable dict."""
        return {
            "document_id": self.document_id,
            "title": self.title,
            "content_snippet": self.content_snippet,
            "source": self.source,
            "page": self.page,
            "score": round(self.score, 3),
        }


@dataclass
class Citation:
    """A complete citation attached to an agent answer.

    Attributes:
        sources: List of source documents supporting the answer.
        answer: The generated answer text.
        confidence: Overall confidence score (0.0 to 1.0).
    """
    sources: list = field(default_factory=list)
    answer: str = ""
    confidence: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to a serializable dict."""
        return {
            "sources": [s.to_dict() for s in self.sources],
            "answer": self.answer,
            "confidence": round(self.confidence, 3),
        }

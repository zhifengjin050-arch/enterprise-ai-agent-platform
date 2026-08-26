"""Citation package for knowledge agent answers.

Provides data models and extraction logic for generating
traceable citations from search results.
"""

from app.citation.extractor import CitationExtractor, extract_citations
from app.citation.models import Citation, CitationSource

__all__ = [
    "Citation",
    "CitationSource",
    "CitationExtractor",
    "extract_citations",
]

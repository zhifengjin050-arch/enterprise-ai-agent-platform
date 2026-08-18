"""Search package - full-text, semantic, and hybrid search for enterprise knowledge.

Provides three search modes:
  - Fulltext: SQLite FTS5 (dev) / PostgreSQL FTS (prod) keyword search
  - Semantic: ChromaDB vector similarity search
  - Hybrid: RRF-based fusion of fulltext and semantic results
"""
from app.search.fulltext import DocumentResult, FullTextSearch
from app.search.hybrid import HybridResult, HybridSearch, rrf_score
from app.search.indexer import KnowledgeIndexer
from app.search.semantic import SemanticResult, SemanticSearch

__all__ = [
    "FullTextSearch",
    "DocumentResult",
    "SemanticSearch",
    "SemanticResult",
    "HybridSearch",
    "HybridResult",
    "rrf_score",
    "KnowledgeIndexer",
]

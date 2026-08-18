"""Vector store package.

Provides vector storage and similarity search capabilities for the knowledge
platform using ChromaDB as the primary backend.

Public API:
    VectorStore          — abstract base class
    VectorSearchResult   — search result dataclass
    ChromaStore          — ChromaDB persistent implementation
"""
from app.vectorstore.base import VectorSearchResult, VectorStore
from app.vectorstore.chroma_store import ChromaStore

__all__ = [
    "VectorStore",
    "VectorSearchResult",
    "ChromaStore",
]

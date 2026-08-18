"""
Knowledge management + Intelligence Layer package.

Asset layer (existing):
- Knowledge models (Document, Category, Tag)
- Classification / Tagging / Lifecycle

Intelligence Layer (Phase 5):
- SmartChunker, DocumentChunk, KnowledgeRetriever, Reranker, KnowledgeGraph, ...

Note: Heavy retrieval imports are lazy via __getattr__ to avoid circular
imports with app.search (which imports app.knowledge.models).
"""

from app.knowledge.chunk_models import DocumentChunk
from app.knowledge.chunk_repository import DocumentChunkRepository
from app.knowledge.chunking import Chunk, SmartChunker, estimate_tokens
from app.knowledge.context_builder import IntelligenceContextBuilder
from app.knowledge.embedding import ChunkEmbeddingService, KnowledgeEmbedding
from app.knowledge.graph import GraphEdge, GraphNode, KnowledgeGraph
from app.knowledge.memory import KnowledgeMemory, knowledge_memory
from app.knowledge.reranker import Reranker

__all__ = [
    "Chunk",
    "SmartChunker",
    "estimate_tokens",
    "DocumentChunk",
    "DocumentChunkRepository",
    "ChunkEmbeddingService",
    "KnowledgeEmbedding",
    "KnowledgeRetriever",
    "RetrievalResult",
    "IntelligenceHybridSearch",
    "KnowledgeHybridSearch",
    "Reranker",
    "GraphNode",
    "GraphEdge",
    "KnowledgeGraph",
    "KnowledgeMemory",
    "knowledge_memory",
    "IntelligenceContextBuilder",
]


def __getattr__(name: str):
    """Lazy export for modules that depend on app.search."""
    if name in ("KnowledgeRetriever", "RetrievalResult"):
        from app.knowledge.retrieval import KnowledgeRetriever, RetrievalResult

        return {"KnowledgeRetriever": KnowledgeRetriever, "RetrievalResult": RetrievalResult}[name]
    if name in ("IntelligenceHybridSearch", "KnowledgeHybridSearch"):
        from app.knowledge.hybrid_search import (
            IntelligenceHybridSearch,
            KnowledgeHybridSearch,
        )

        return {
            "IntelligenceHybridSearch": IntelligenceHybridSearch,
            "KnowledgeHybridSearch": KnowledgeHybridSearch,
        }[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

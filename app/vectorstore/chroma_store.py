"""ChromaDB vector store implementation.

Provides a VectorStore adapter wrapping ChromaDB's collection-based
vector storage and similarity search capabilities.

Note: chromadb is imported lazily to avoid hard dependency on
Windows C++ build tools during development.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.core.config import get_settings
from app.vectorstore.base import VectorSearchResult, VectorStore


class ChromaStore(VectorStore):
    """ChromaDB-based vector store implementation.

    Stores document embeddings in ChromaDB with metadata filtering support.
    Designed for knowledge platform semantic search (not chatbot RAG).
    """

    def __init__(
        self,
        collection_name: Optional[str] = None,
        persistent_path: Optional[str] = None,
    ) -> None:
        self._chromadb = None
        self._chroma_settings_cls = None

        try:
            import chromadb as _cdb
            from chromadb.config import Settings as _cs

            self._chromadb = _cdb
            self._chroma_settings_cls = _cs
        except ImportError:
            pass

        settings = get_settings()
        self._collection_name = (
            collection_name or settings.chroma_collection or "knowledge_docs"
        )
        self._persistent_path = persistent_path or settings.chroma_path or "./data/chroma"
        self._client: Any = None
        self._collection: Any = None

    def _ensure_client(self) -> None:
        """Initialize ChromaDB PersistentClient if not already done.

        Raises:
            RuntimeError: If chromadb package is not installed.
        """
        if self._client is not None:
            return

        if self._chromadb is None:
            raise RuntimeError(
                "ChromaDB is not installed. Run: pip install chromadb"
            )

        self._client = self._chromadb.PersistentClient(
            path=self._persistent_path,
            settings=self._chroma_settings_cls(anonymized_telemetry=False),
        )

    async def _get_collection(self) -> Any:
        """Lazy-load the ChromaDB collection."""
        self._ensure_client()
        if self._collection is None:
            try:
                self._collection = self._client.get_collection(
                    self._collection_name
                )
            except ValueError:
                self._collection = self._client.create_collection(
                    self._collection_name
                )
        return self._collection

    async def add(
        self,
        document_id: str,
        embedding: List[float],
        metadata: Optional[Dict[str, Any]] = None,
        content: Optional[str] = None,
    ) -> None:
        """Add a single document vector."""
        collection = await self._get_collection()
        collection.add(
            ids=[document_id],
            embeddings=[embedding],
            metadatas=[metadata or {}],
            documents=[content] if content else None,
        )

    async def add_batch(
        self,
        ids: List[str],
        embeddings: List[List[float]],
        metadatas: Optional[List[Dict[str, Any]]] = None,
        contents: Optional[List[str]] = None,
    ) -> None:
        """Add multiple document vectors in batch."""
        collection = await self._get_collection()
        collection.add(
            ids=ids,
            embeddings=embeddings,
            metadatas=metadatas or [{}] * len(ids),
            documents=contents,
        )

    async def query(
        self,
        query_embedding: List[float],
        top_k: int = 10,
        metadata_filter: Optional[Dict[str, Any]] = None,
    ) -> List[VectorSearchResult]:
        """Search for similar documents by embedding.

        Returns VectorSearchResult objects with document_id extracted
        from the stored metadata.
        """
        collection = await self._get_collection()

        where = None
        if metadata_filter:
            where = {k: v for k, v in metadata_filter.items() if v is not None}

        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=min(top_k, 100),
            where=where,
        )

        output: List[VectorSearchResult] = []
        if results["ids"]:
            for i, doc_id in enumerate(results["ids"][0]):
                meta: Dict[str, Any] = (
                    results["metadatas"][0][i] if results.get("metadatas") else {}
                )
                output.append(
                    VectorSearchResult(
                        id=doc_id,
                        document_id=meta.get("document_id", doc_id),
                        score=(
                            float(results["distances"][0][i])
                            if results.get("distances")
                            else 0.0
                        ),
                        metadata=meta,
                        content=(
                            results["documents"][0][i]
                            if results.get("documents")
                            else None
                        ),
                    )
                )
        return output

    async def delete(self, document_id: str) -> None:
        """Remove a single document by its id."""
        collection = await self._get_collection()
        collection.delete(ids=[document_id])

    async def delete_batch(self, ids: List[str]) -> None:
        """Remove multiple documents."""
        collection = await self._get_collection()
        collection.delete(ids=ids)

    async def update(
        self,
        document_id: str,
        embedding: Optional[List[float]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        content: Optional[str] = None,
    ) -> None:
        """Update an existing document."""
        collection = await self._get_collection()
        collection.update(
            ids=[document_id],
            embeddings=[embedding] if embedding else None,
            metadatas=[metadata] if metadata else None,
            documents=[content] if content else None,
        )

    async def count(self) -> int:
        """Return total document count."""
        collection = await self._get_collection()
        return collection.count()

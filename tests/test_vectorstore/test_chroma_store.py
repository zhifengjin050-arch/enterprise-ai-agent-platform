"""Tests for ChromaStore implementation with fully mocked internals.

Instead of patching sys.modules (which conflicts with other test modules
that import chroma_store at collection time), this test directly sets
store._chromadb and store._chroma_settings_cls to MagicMock objects,
bypassing the lazy-import mechanism entirely.
"""

from __future__ import annotations

from typing import Any, List
from unittest.mock import MagicMock

import pytest

from app.vectorstore.base import VectorSearchResult


def _make_mock_chromadb() -> tuple[Any, Any]:
    """Build a mock chromadb module and a pre-configured mock collection."""
    mock_coll = MagicMock()
    mock_coll.query.return_value = {
        "ids": [["emb_d1", "emb_d2"]],
        "distances": [[0.1, 0.3]],
        "metadatas": [
            [
                {"document_id": "d1", "title": "Doc A"},
                {"document_id": "d2", "title": "Doc B"},
            ]
        ],
        "documents": [["content A", "content B"]],
    }
    mock_coll.count.return_value = 2

    mock_client = MagicMock()
    mock_client.get_collection.side_effect = ValueError("not found")
    mock_client.create_collection.return_value = mock_coll

    mock_chromadb = MagicMock()
    mock_chromadb.PersistentClient.return_value = mock_client

    mock_settings_cls = MagicMock()
    mock_settings_cls.return_value = MagicMock()

    return mock_chromadb, mock_settings_cls


@pytest.fixture(autouse=True)
def _patch_chromadb_on_store() -> None:
    """Fixtue is a no-op; each test patches its own ChromaStore instance."""
    return None


@pytest.mark.asyncio
async def test_chroma_store_add() -> None:
    """Add a single document vector to ChromaDB."""
    from app.vectorstore.chroma_store import ChromaStore

    store = ChromaStore(collection_name="test_coll", persistent_path="/tmp/test_chroma")
    store._chromadb, store._chroma_settings_cls = _make_mock_chromadb()

    await store.add(
        document_id="emb_d1",
        embedding=[0.1, 0.2, 0.3],
        metadata={"document_id": "d1", "title": "Doc A"},
    )
    col = await store._get_collection()
    col.add.assert_called_once()


@pytest.mark.asyncio
async def test_chroma_store_add_batch() -> None:
    """Add multiple document vectors in a single batch call."""
    from app.vectorstore.chroma_store import ChromaStore

    store = ChromaStore(collection_name="test_coll", persistent_path="/tmp/test_chroma")
    store._chromadb, store._chroma_settings_cls = _make_mock_chromadb()

    await store.add_batch(
        ids=["emb_d1", "emb_d2"],
        embeddings=[[0.1, 0.2], [0.3, 0.4]],
        metadatas=[{"document_id": "d1"}, {"document_id": "d2"}],
    )
    col = await store._get_collection()
    col.add.assert_called_once()


@pytest.mark.asyncio
async def test_chroma_store_query() -> None:
    """Query ChromaDB and verify VectorSearchResult mapping."""
    from app.vectorstore.chroma_store import ChromaStore

    store = ChromaStore(collection_name="test_coll", persistent_path="/tmp/test_chroma")
    store._chromadb, store._chroma_settings_cls = _make_mock_chromadb()

    results: List[VectorSearchResult] = await store.query(
        query_embedding=[0.1, 0.2, 0.3],
        top_k=2,
    )

    assert len(results) == 2
    assert results[0].document_id == "d1"
    assert results[0].score == 0.1
    assert results[0].content == "content A"
    assert results[1].document_id == "d2"


@pytest.mark.asyncio
async def test_chroma_store_delete() -> None:
    """Delete a single document from ChromaDB by its id."""
    from app.vectorstore.chroma_store import ChromaStore

    store = ChromaStore(collection_name="test_coll", persistent_path="/tmp/test_chroma")
    store._chromadb, store._chroma_settings_cls = _make_mock_chromadb()

    await store.delete("emb_d1")
    col = await store._get_collection()
    col.delete.assert_called_once_with(ids=["emb_d1"])


@pytest.mark.asyncio
async def test_chroma_store_count() -> None:
    """Return the total number of indexed documents."""
    from app.vectorstore.chroma_store import ChromaStore

    store = ChromaStore(collection_name="test_coll", persistent_path="/tmp/test_chroma")
    store._chromadb, store._chroma_settings_cls = _make_mock_chromadb()

    count = await store.count()
    assert count == 2


@pytest.mark.asyncio
async def test_chroma_store_update() -> None:
    """Update an existing document's embedding and metadata."""
    from app.vectorstore.chroma_store import ChromaStore

    store = ChromaStore(collection_name="test_coll", persistent_path="/tmp/test_chroma")
    store._chromadb, store._chroma_settings_cls = _make_mock_chromadb()

    await store.update(
        document_id="emb_d1",
        embedding=[0.5, 0.6, 0.7],
        metadata={"document_id": "d1", "title": "Updated"},
    )
    col = await store._get_collection()
    col.update.assert_called_once()


@pytest.mark.asyncio
async def test_chroma_store_not_installed() -> None:
    """When chromadb is not installed, ChromaStore should raise RuntimeError."""
    from app.vectorstore.chroma_store import ChromaStore

    store = ChromaStore()
    store._chromadb = None  # Simulate chromadb not being installed
    store._chroma_settings_cls = None
    with pytest.raises(RuntimeError, match="ChromaDB is not installed"):
        await store._get_collection()

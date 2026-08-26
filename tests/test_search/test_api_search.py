"""Tests for search API endpoints with mocked engines."""

from __future__ import annotations

from typing import Any, Dict
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@patch("app.api.search.get_semantic_search")
def test_semantic_search_endpoint(mock_get_semantic: AsyncMock, client: TestClient) -> None:
    mock_engine = AsyncMock()
    mock_engine.search.return_value = [
        type(
            "SemanticResult",
            (),
            {
                "id": "doc-1",
                "title": "Test Doc",
                "content": "content",
                "score": 0.95,
                "metadata": {"doc_type": "sop"},
            },
        )(),
    ]
    mock_get_semantic.return_value = mock_engine

    response = client.get("/api/search/semantic?q=deploy&top_k=5")
    assert response.status_code == 200
    data: Dict[str, Any] = response.json()
    assert data["query"] == "deploy"
    assert data["total"] == 1
    assert data["results"][0]["id"] == "doc-1"
    assert data["results"][0]["score"] == 0.95


@patch("app.api.search.get_fulltext_search")
def test_fulltext_search_endpoint(mock_get_fts: AsyncMock, client: TestClient) -> None:
    mock_engine = AsyncMock()
    mock_engine.search.return_value = [
        type(
            "DocumentResult",
            (),
            {
                "id": "doc-1",
                "title": "Doc",
                "snippet": "...",
                "score": 1.0,
                "doc_type": "sop",
                "metadata": {},
            },
        )(),
    ]
    mock_get_fts.return_value = mock_engine

    response = client.get("/api/search/fulltext?q=kubernetes&limit=10")
    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "fulltext"
    assert data["total"] == 1


@patch("app.api.search.get_hybrid_search")
def test_hybrid_search_endpoint(mock_get_hybrid: AsyncMock, client: TestClient) -> None:
    mock_engine = AsyncMock()
    mock_engine.search.return_value = [
        type(
            "HybridResult",
            (),
            {
                "id": "doc-1",
                "title": "Doc",
                "snippet": "...",
                "score": 0.032,
                "metadata": {},
            },
        )(),
    ]
    mock_get_hybrid.return_value = mock_engine

    response = client.get("/api/search/hybrid?q=deploy&top_k=5")
    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "hybrid"
    assert data["total"] == 1


@patch("app.api.search.get_indexer")
def test_rebuild_index_endpoint(mock_get_indexer: AsyncMock, client: TestClient) -> None:
    mock_indexer = AsyncMock()
    mock_indexer.rebuild_index.return_value = {"total": 10, "indexed": 8, "failed": 2}
    mock_get_indexer.return_value = mock_indexer

    response = client.post("/api/search/rebuild")
    assert response.status_code == 200
    data = response.json()
    assert data["action"] == "rebuild"
    assert data["indexed"] == 8

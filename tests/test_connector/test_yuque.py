"""Tests for YuqueConnector."""

from __future__ import annotations

from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.connector.exceptions import AuthenticationError
from app.connector.yuque import YuqueConnector


class TestYuqueConnector:
    """Tests for YuqueConnector."""

    def setup_method(self) -> None:
        """Create a YuqueConnector instance with test config."""
        self.config: Dict[str, Any] = {
            "token": "test_token",
        }
        self.connector = YuqueConnector(config=self.config)

    def test_init(self) -> None:
        """Test initialization."""
        assert self.connector.name == "Yuque"
        assert self.connector.connector_type == "yuque"
        assert self.connector._token == "test_token"

    def test_init_no_token(self) -> None:
        """Test initialization without token."""
        conn = YuqueConnector()
        assert conn._token == ""

    @patch("httpx.AsyncClient")
    async def test_test_connection_success(self, mock_client: AsyncMock) -> None:
        """Test successful connection test."""
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json = MagicMock(
            return_value={"data": {"login": "test_user", "name": "Test"}}
        )

        mock_instance = AsyncMock()
        mock_instance.request.return_value = mock_response
        mock_client.return_value.__aenter__.return_value = mock_instance

        result = await self.connector.test_connection()
        assert result is True

    @patch("httpx.AsyncClient")
    async def test_test_connection_failure(self, mock_client: AsyncMock) -> None:
        """Test failed connection test."""
        mock_response = AsyncMock()
        mock_response.status_code = 401
        mock_response.json = MagicMock(return_value={"message": "Unauthorized"})

        mock_instance = AsyncMock()
        mock_instance.request.return_value = mock_response
        mock_client.return_value.__aenter__.return_value = mock_instance

        result = await self.connector.test_connection()
        assert result is False

    async def test_fetch_documents_no_token(self) -> None:
        """Test that fetch_documents raises without token."""
        conn = YuqueConnector()
        with pytest.raises(AuthenticationError):
            await conn.fetch_documents()

    @patch("httpx.AsyncClient")
    async def test_fetch_documents_with_namespace(self, mock_client: AsyncMock) -> None:
        """Test fetch_documents with a specific namespace."""
        conn = YuqueConnector(config={"token": "tok", "namespace": "org/repo"})

        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json = MagicMock(
            return_value=[
                {"slug": "doc1", "title": "Doc 1", "updated_at": "2026-01-01T00:00:00Z"},
                {"slug": "doc2", "title": "Doc 2", "updated_at": "2026-01-02T00:00:00Z"},
            ]
        )

        mock_instance = AsyncMock()
        mock_instance.request.return_value = mock_response
        mock_client.return_value.__aenter__.return_value = mock_instance

        docs = await conn.fetch_documents()
        assert len(docs) == 2
        assert docs[0].id == "org/repo:doc1"
        assert docs[1].id == "org/repo:doc2"

    @patch("httpx.AsyncClient")
    async def test_get_document(self, mock_client: AsyncMock) -> None:
        """Test get_document returns full content."""
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json = MagicMock(
            return_value={
                "data": {
                    "title": "Test Doc",
                    "body": "# Hello\n\nThis is markdown content.",
                    "updated_at": "2026-01-01T00:00:00Z",
                }
            }
        )

        mock_instance = AsyncMock()
        mock_instance.request.return_value = mock_response
        mock_client.return_value.__aenter__.return_value = mock_instance

        doc = await self.connector.get_document("org/repo:test-doc")
        assert doc is not None
        assert doc.title == "Test Doc"
        assert "Hello" in doc.content
        assert doc.id == "org/repo:test-doc"

    @patch("httpx.AsyncClient")
    async def test_get_document_not_found(self, mock_client: AsyncMock) -> None:
        """Test get_document returns None for missing doc."""
        mock_response = AsyncMock()
        mock_response.status_code = 404

        mock_instance = AsyncMock()
        mock_instance.request.return_value = mock_response
        mock_client.return_value.__aenter__.return_value = mock_instance

        doc = await self.connector.get_document("org/repo:nonexistent")
        assert doc is None

    async def test_get_document_invalid_id(self) -> None:
        """Test get_document with invalid ID format."""
        doc = await self.connector.get_document("invalid-no-namespace")
        assert doc is None

"""Tests for FeishuConnector."""

from __future__ import annotations

from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.connector.exceptions import AuthenticationError
from app.connector.feishu import FeishuConnector, _convert_to_markdown, _extract_block_text


class TestFeishuConnector:
    """Tests for FeishuConnector."""

    def setup_method(self) -> None:
        """Create a FeishuConnector instance with test config."""
        self.config: Dict[str, Any] = {
            "app_id": "test_app_id",
            "app_secret": "test_app_secret",
        }
        self.connector = FeishuConnector(config=self.config)

    def test_init(self) -> None:
        """Test initialization."""
        assert self.connector.name == "Feishu"
        assert self.connector.connector_type == "feishu"
        assert self.connector._app_id == "test_app_id"
        assert self.connector._app_secret == "test_app_secret"

    def test_init_no_credentials(self) -> None:
        """Test initialization without credentials."""
        conn = FeishuConnector()
        assert conn._app_id == ""
        assert conn._app_secret == ""

    @patch("httpx.AsyncClient")
    async def test_test_connection_success(self, mock_client: AsyncMock) -> None:
        """Test successful connection test."""
        # httpx.Response.json() is sync, so use MagicMock for responses
        mock_post_response = AsyncMock()
        mock_post_response.status_code = 200
        mock_post_response.json = MagicMock(
            return_value={
                "code": 0,
                "msg": "ok",
                "tenant_access_token": "test_token",
                "expire": 7200,
            }
        )

        mock_instance = AsyncMock()
        mock_instance.post.return_value = mock_post_response
        mock_client.return_value.__aenter__.return_value = mock_instance

        result = await self.connector.test_connection()
        assert result is True

    @patch("httpx.AsyncClient")
    async def test_test_connection_failure(self, mock_client: AsyncMock) -> None:
        """Test failed connection test."""
        mock_post_response = AsyncMock()
        mock_post_response.status_code = 401
        mock_post_response.json = MagicMock(return_value={"code": -1, "msg": "invalid credentials"})

        mock_instance = AsyncMock()
        mock_instance.post.return_value = mock_post_response
        mock_client.return_value.__aenter__.return_value = mock_instance

        result = await self.connector.test_connection()
        assert result is False

    async def test_fetch_documents_no_token(self) -> None:
        """Test that fetch_documents raises AuthenticationError without token."""
        conn = FeishuConnector()  # No credentials
        with pytest.raises(AuthenticationError):
            await conn.fetch_documents()

    @patch("httpx.AsyncClient")
    async def test_get_document_not_found(self, mock_client: AsyncMock) -> None:
        """Test get_document returns None for non-existent doc."""
        # Token auth response
        mock_auth = AsyncMock()
        mock_auth.status_code = 200
        mock_auth.json = MagicMock(
            return_value={"code": 0, "tenant_access_token": "tok", "expire": 7200}
        )

        mock_instance = AsyncMock()
        mock_instance.post.return_value = mock_auth

        # Make the GET request for doc content return 404
        mock_404 = AsyncMock()
        mock_404.status_code = 404
        mock_404.text = "Not Found"
        mock_instance.request.return_value = mock_404
        mock_client.return_value.__aenter__.return_value = mock_instance

        result = await self.connector.get_document("nonexistent")
        assert result is None

    def test_convert_to_markdown_empty(self) -> None:
        """Test markdown conversion with empty content."""
        md = _convert_to_markdown("", "Empty")
        assert "# Empty" in md
        assert "Empty document" in md

    def test_convert_to_markdown_plain_text(self) -> None:
        """Test markdown conversion with plain text (not JSON)."""
        md = _convert_to_markdown("Hello world", "Plain")
        assert "# Plain" in md
        assert "Hello world" in md

    def test_convert_to_markdown_headings(self) -> None:
        """Test heading extraction for different levels."""
        raw = (
            '{"blocks": [{"block_type": "heading2", "text": {"elements": '
            '[{"text_run": {"content": "Section 1"}}]}}, '
            '{"block_type": "heading3", "text": {"elements": '
            '[{"text_run": {"content": "Sub Section"}}]}}]}'
        )
        md = _convert_to_markdown(raw, "Doc")
        assert "## Section 1" in md
        assert "### Sub Section" in md

    def test_extract_block_text_bullet(self) -> None:
        """Test bullet extraction."""
        lines: list = []
        _extract_block_text(
            {"block_type": "bullet", "text": {"elements": [{"text_run": {"content": "Item 1"}}]}},
            lines,
        )
        assert any("- Item 1" in l for l in lines)

    def test_convert_to_markdown_json_text(self) -> None:
        """Test JSON with direct text field."""
        md = _convert_to_markdown('{"text": "Direct text content."}', "JSON Doc")
        assert "Direct text content." in md

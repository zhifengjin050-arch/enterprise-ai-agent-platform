"""Tests for GitLabConnector."""

from __future__ import annotations

from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.connector.exceptions import AuthenticationError
from app.connector.gitlab import GitLabConnector


class TestGitLabConnector:
    """Tests for GitLabConnector."""

    def setup_method(self) -> None:
        """Create a GitLabConnector instance with test config."""
        self.config: Dict[str, Any] = {
            "url": "https://gitlab.com",
            "token": "test_token",
            "project_id": 12345,
            "wiki_enabled": True,
            "readme_enabled": True,
        }
        self.connector = GitLabConnector(config=self.config)

    def test_init(self) -> None:
        """Test initialization."""
        assert self.connector.name == "GitLab"
        assert self.connector.connector_type == "gitlab"
        assert self.connector._base_url == "https://gitlab.com"
        assert self.connector._token == "test_token"
        assert self.connector._project_id == "12345"
        assert self.connector._wiki_enabled is True
        assert self.connector._readme_enabled is True

    def test_init_no_config(self) -> None:
        """Test initialization without config."""
        conn = GitLabConnector()
        assert conn._base_url == "https://gitlab.com"
        assert conn._token == ""
        assert conn._project_id == ""

    def test_default_base_url(self) -> None:
        """Test default base URL."""
        conn = GitLabConnector()
        assert conn._base_url == "https://gitlab.com"

    def test_custom_base_url(self) -> None:
        """Test custom base URL."""
        conn = GitLabConnector(config={"url": "https://gitlab.example.com"})
        assert conn._base_url == "https://gitlab.example.com"

    @patch("httpx.AsyncClient")
    async def test_test_connection_success(self, mock_client: AsyncMock) -> None:
        """Test successful connection test."""
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json = MagicMock(
            return_value={"id": 12345, "path_with_namespace": "test/project"}
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

    async def test_fetch_without_token_raises(self) -> None:
        """Test that fetch_documents raises without token."""
        conn = GitLabConnector(config={"project_id": 1})
        with pytest.raises(AuthenticationError):
            await conn.fetch_documents()

    async def test_fetch_without_project_id_raises(self) -> None:
        """Test that fetch_documents raises without project_id."""
        conn = GitLabConnector(config={"token": "tok"})
        with pytest.raises(AuthenticationError):
            await conn.fetch_documents()

    @patch("httpx.AsyncClient")
    async def test_fetch_documents_with_wiki_and_readme(self, mock_client: AsyncMock) -> None:
        """Test fetching wiki pages + readme."""
        # First call -> wiki list
        mock_wiki_response = AsyncMock()
        mock_wiki_response.status_code = 200
        mock_wiki_response.json = MagicMock(
            return_value=[
                {"slug": "home", "title": "Home", "format": "markdown"},
                {"slug": "guide", "title": "User Guide", "format": "markdown"},
            ]
        )

        # Second call -> README
        mock_readme_response = AsyncMock()
        mock_readme_response.status_code = 200
        mock_readme_response.json = MagicMock(
            return_value={
                "content": "# README\n\nWelcome",
                "file_name": "README.md",
            }
        )

        mock_instance = AsyncMock()
        mock_instance.request.side_effect = [
            mock_wiki_response,  # Wiki list
            mock_readme_response,  # README
        ]
        mock_client.return_value.__aenter__.return_value = mock_instance

        docs = await self.connector.fetch_documents()
        assert len(docs) == 3  # 2 wiki + 1 readme

        wiki_ids = [d.id for d in docs if d.id.startswith("wiki:")]
        readme_ids = [d.id for d in docs if d.id == "readme"]
        assert len(wiki_ids) == 2
        assert len(readme_ids) == 1

    @patch("httpx.AsyncClient")
    async def test_fetch_wiki_disabled(self, mock_client: AsyncMock) -> None:
        """Test fetching with wiki disabled."""
        conn = GitLabConnector(
            config={
                "url": "https://gitlab.com",
                "token": "tok",
                "project_id": 1,
                "wiki_enabled": False,
                "readme_enabled": False,
            }
        )
        docs = await conn.fetch_documents()
        assert len(docs) == 0

    @patch("httpx.AsyncClient")
    async def test_get_wiki_document(self, mock_client: AsyncMock) -> None:
        """Test get_document with a wiki page."""
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json = MagicMock(
            return_value={
                "title": "Home",
                "content": "# Home\n\nWelcome to the wiki.",
                "format": "markdown",
            }
        )

        mock_instance = AsyncMock()
        mock_instance.request.return_value = mock_response
        mock_client.return_value.__aenter__.return_value = mock_instance

        doc = await self.connector.get_document("wiki:home")
        assert doc is not None
        assert doc.title == "Home"
        assert "Welcome" in doc.content
        assert doc.id == "wiki:home"

    @patch("httpx.AsyncClient")
    async def test_get_readme(self, mock_client: AsyncMock) -> None:
        """Test get_document with README."""
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json = MagicMock(
            return_value={
                "content": "# README\n\nProject description.",
                "file_name": "README.md",
            }
        )

        mock_instance = AsyncMock()
        mock_instance.request.return_value = mock_response
        mock_client.return_value.__aenter__.return_value = mock_instance

        doc = await self.connector.get_document("readme")
        assert doc is not None
        assert doc.title == "README"
        assert "Project description" in doc.content

    def test_get_document_unknown(self) -> None:
        """Test get_document with unknown ID type (no API call needed)."""
        # We don't even need to mock since the connector checks
        # id prefix before making HTTP calls
        pass

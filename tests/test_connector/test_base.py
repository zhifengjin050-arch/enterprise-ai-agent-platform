"""Tests for connector base abstraction: BaseConnector, ConnectorDocument."""

from __future__ import annotations

from typing import List, Optional

import pytest

from app.connector.base import BaseConnector, ConnectorDocument
from app.connector.exceptions import (
    AuthenticationError,
    ConnectionError,
    ConnectorError,
    NotFoundError,
    SyncError,
)


class TestConnectorDocument:
    """Tests for the ConnectorDocument dataclass."""

    def test_defaults(self) -> None:
        """Test default field values."""
        doc = ConnectorDocument()
        assert doc.id == ""
        assert doc.title == ""
        assert doc.content == ""
        assert doc.url == ""
        assert doc.updated_at is None
        assert doc.metadata == {}

    def test_with_values(self) -> None:
        """Test creating with explicit values."""
        doc = ConnectorDocument(
            id="123",
            title="Test Doc",
            content="# Hello",
            url="https://example.com/doc/123",
            updated_at="2026-01-01T00:00:00Z",
            metadata={"tags": ["test"], "author": "tester"},
        )
        assert doc.id == "123"
        assert doc.title == "Test Doc"
        assert doc.content == "# Hello"
        assert doc.url == "https://example.com/doc/123"
        assert doc.updated_at == "2026-01-01T00:00:00Z"
        assert doc.metadata["tags"] == ["test"]
        assert doc.metadata["author"] == "tester"

    def test_to_dict(self) -> None:
        """Test serialization to dict."""
        doc = ConnectorDocument(
            id="abc",
            title="Sample",
            content="body",
            url="https://example.com",
            updated_at="2026-06-15T10:00:00Z",
            metadata={"key": "val"},
        )
        d = doc.to_dict()
        assert d["id"] == "abc"
        assert d["title"] == "Sample"
        assert d["content"] == "body"
        assert d["url"] == "https://example.com"
        assert d["updated_at"] == "2026-06-15T10:00:00Z"
        assert d["metadata"] == {"key": "val"}

    def test_to_dict_fallback_updated_at(self) -> None:
        """Test that to_dict generates updated_at when None."""
        doc = ConnectorDocument(id="x", title="T")
        d = doc.to_dict()
        assert d["updated_at"] is not None  # Should have generated an isoformat string


class TestConnectorError:
    """Tests for custom exception hierarchy."""

    def test_connector_error_base(self) -> None:
        """Test base exception."""
        exc = ConnectorError("something went wrong")
        assert str(exc) == "something went wrong"
        assert exc.message == "something went wrong"

    def test_connection_error(self) -> None:
        """Test ConnectionError (our exception, not built-in)."""
        exc = ConnectionError(source="Feishu", detail="timeout")
        assert "Feishu" in str(exc)
        assert "timeout" in str(exc)
        assert exc.source == "Feishu"
        assert issubclass(ConnectionError, ConnectorError)

    def test_connection_error_no_detail(self) -> None:
        """Test ConnectionError without detail."""
        exc = ConnectionError(source="GitLab")
        assert "GitLab" in str(exc)

    def test_authentication_error(self) -> None:
        """Test AuthenticationError."""
        exc = AuthenticationError(source="Yuque", detail="invalid token")
        assert "Yuque" in str(exc)
        assert "invalid token" in str(exc)
        assert exc.source == "Yuque"
        assert issubclass(AuthenticationError, ConnectorError)

    def test_not_found_error(self) -> None:
        """Test NotFoundError."""
        exc = NotFoundError(resource="Document 123", source="Feishu")
        assert "Document 123" in str(exc)
        assert "Feishu" in str(exc)
        assert exc.resource == "Document 123"
        assert issubclass(NotFoundError, ConnectorError)

    def test_sync_error(self) -> None:
        """Test SyncError."""
        exc = SyncError(source="GitLab", detail="connection lost")
        assert "GitLab" in str(exc)
        assert "connection lost" in str(exc)
        assert exc.source == "GitLab"
        assert issubclass(SyncError, ConnectorError)

    def test_sync_error_no_detail(self) -> None:
        """Test SyncError without detail."""
        exc = SyncError(source="Yuque")
        assert "Yuque" in str(exc)


class TestBaseConnector:
    """Tests for BaseConnector abstract class."""

    def test_abstract_cannot_instantiate(self) -> None:
        """Verify BaseConnector cannot be instantiated directly."""
        with pytest.raises(TypeError):
            BaseConnector()  # type: ignore

    async def test_concrete_subclass(self) -> None:
        """Test that a minimal concrete subclass works."""

        class MinimalConnector(BaseConnector):
            name: str = "Minimal"
            connector_type: str = "minimal"

            async def test_connection(self) -> bool:
                return True

            async def fetch_documents(self) -> List[ConnectorDocument]:
                return []

            async def get_document(self, document_id: str) -> Optional[ConnectorDocument]:
                return None

            async def sync(
                self,
                sync_mode: str = "full",
                cursor: Optional[str] = None,
            ) -> List[ConnectorDocument]:
                return []

        conn = MinimalConnector(config={"key": "val"})
        assert conn._config == {"key": "val"}
        assert conn.name == "Minimal"
        assert conn.connector_type == "minimal"
        result = await conn.test_connection()
        assert result is True
        meta = conn.get_metadata()
        assert meta["name"] == "Minimal"
        assert meta["type"] == "minimal"
        assert meta["version"] == "0.1.0"
        assert "capabilities" in meta

    def test_get_metadata_unconfigured(self) -> None:
        """Test metadata when no config provided."""

        class EmptyConnector(BaseConnector):
            name: str = "Empty"
            connector_type: str = "empty"

            async def test_connection(self) -> bool:
                return False

            async def fetch_documents(self) -> List[ConnectorDocument]:
                return []

            async def get_document(self, document_id: str) -> Optional[ConnectorDocument]:
                return None

            async def sync(
                self,
                sync_mode: str = "full",
                cursor: Optional[str] = None,
            ) -> List[ConnectorDocument]:
                return []

        conn = EmptyConnector()
        meta = conn.get_metadata()
        assert meta["name"] == "Empty"
        assert meta["type"] == "empty"
        assert "capabilities" in meta

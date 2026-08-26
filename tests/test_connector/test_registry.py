"""Tests for ConnectorRegistry."""

from __future__ import annotations

from typing import List, Optional

import pytest

from app.connector.base import BaseConnector, ConnectorDocument
from app.connector.registry import ConnectorRegistry


class DummyConnector(BaseConnector):
    """Dummy connector for testing."""

    name: str = "Dummy"
    connector_type: str = "dummy"

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


class AnotherDummyConnector(BaseConnector):
    """Another dummy connector."""

    name: str = "Another"
    connector_type: str = "another"

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


class NotAConnector:
    """Class that does NOT subclass BaseConnector."""

    pass


class TestConnectorRegistry:
    """Tests for the ConnectorRegistry."""

    def setup_method(self) -> None:
        self.registry = ConnectorRegistry()

    def test_register_and_create(self) -> None:
        """Test registration and instantiation."""
        self.registry.register("dummy", DummyConnector)
        conn = self.registry.create("dummy", config={"foo": "bar"})
        assert isinstance(conn, DummyConnector)
        assert conn._config == {"foo": "bar"}
        assert conn.name == "Dummy"

    def test_register_duplicate_raises(self) -> None:
        """Test registering the same type twice raises ValueError."""
        self.registry.register("dummy", DummyConnector)
        with pytest.raises(ValueError, match="already registered"):
            self.registry.register("dummy", AnotherDummyConnector)

    def test_register_non_subclass_raises(self) -> None:
        """Test registering a non-BaseConnector subclass raises TypeError."""
        with pytest.raises(TypeError, match="must subclass BaseConnector"):
            self.registry.register("bad", NotAConnector)  # type: ignore

    def test_create_unknown_type_raises(self) -> None:
        """Test creating an unregistered connector raises ValueError."""
        with pytest.raises(ValueError, match="Unknown connector type"):
            self.registry.create("nonexistent")

    def test_unregister(self) -> None:
        """Test unregistering a connector type."""
        self.registry.register("dummy", DummyConnector)
        assert self.registry.is_registered("dummy") is True
        self.registry.unregister("dummy")
        assert self.registry.is_registered("dummy") is False

    def test_list_types(self) -> None:
        """Test listing registered types."""
        self.registry.register("dummy", DummyConnector)
        self.registry.register("another", AnotherDummyConnector)
        types = self.registry.list_types()
        assert types["dummy"] == "Dummy"
        assert types["another"] == "Another"

    def test_is_registered(self) -> None:
        """Test is_registered()."""
        self.registry.register("dummy", DummyConnector)
        assert self.registry.is_registered("dummy") is True
        assert self.registry.is_registered("unknown") is False

    def test_multiple_create(self) -> None:
        """Test creating multiple instances independently."""
        self.registry.register("dummy", DummyConnector)
        c1 = self.registry.create("dummy", config={"a": 1})
        c2 = self.registry.create("dummy", config={"b": 2})
        assert c1._config == {"a": 1}
        assert c2._config == {"b": 2}
        assert c1 is not c2

    def test_error_message_lists_available(self) -> None:
        """Test that the error message lists available types."""
        self.registry.register("dummy", DummyConnector)
        self.registry.register("another", AnotherDummyConnector)
        with pytest.raises(ValueError) as excinfo:
            self.registry.create("nope")
        assert "another" in str(excinfo.value)
        assert "dummy" in str(excinfo.value)

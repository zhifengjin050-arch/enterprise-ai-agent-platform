"""Tests for ConnectorFactory."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import pytest

from app.connector.base import BaseConnector, ConnectorDocument
from app.connector.capability import ConnectorCapability
from app.connector.factory import ConnectorFactory
from app.connector.registry import ConnectorRegistry
from app.core.exceptions import ConnectorConfigError


# ── Test connectors ──


class SearchConnector(BaseConnector):
    """A connector that supports search."""
    name: str = "Search"
    connector_type: str = "search"
    capabilities: List[ConnectorCapability] = [ConnectorCapability.DOCUMENT_READ]

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


# ── Tests ──


class TestConnectorFactory:
    """Tests for the ConnectorFactory."""

    def setup_method(self) -> None:
        self.registry = ConnectorRegistry()
        self.factory = ConnectorFactory()

        # Use the factory's internal registry reference for registration
        # Since factory uses the module-level connector_registry singleton,
        # we need to register on that singleton.
        from app.connector.registry import connector_registry as main_registry
        self._main_registry = main_registry

    @pytest.mark.asyncio
    async def test_create_success(self) -> None:
        """Test factory.create returns an initialised connector."""
        self._main_registry.register("search", SearchConnector)
        try:
            conn = await self.factory.create("search", config={"key": "val"})
            assert isinstance(conn, SearchConnector)
            assert conn._config == {"key": "val"}
        finally:
            self._main_registry.unregister("search")

    @pytest.mark.asyncio
    async def test_create_unknown_type(self) -> None:
        """Test factory.create raises for unknown type."""
        with pytest.raises(ConnectorConfigError, match="Unknown connector type"):
            await self.factory.create("nonexistent")

    @pytest.mark.asyncio
    async def test_create_raw(self) -> None:
        """Test create_raw creates without lifecycle initialisation."""
        self._main_registry.register("search", SearchConnector)
        try:
            conn = await self.factory.create_raw("search", config={"key": "val"})
            assert isinstance(conn, SearchConnector)
            assert conn._config == {"key": "val"}
        finally:
            self._main_registry.unregister("search")

    @pytest.mark.asyncio
    async def test_create_raw_unknown(self) -> None:
        """Test create_raw raises for unknown type."""
        with pytest.raises(ConnectorConfigError, match="Unknown connector type"):
            await self.factory.create_raw("nonexistent")
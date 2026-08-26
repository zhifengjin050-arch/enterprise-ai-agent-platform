"""Tests for the enhanced ConnectorRegistry (metadata, capabilities, discovery)."""

from __future__ import annotations

from typing import List, Optional

import pytest

from app.connector.base import BaseConnector, ConnectorDocument
from app.connector.capability import ConnectorCapability
from app.connector.registry import ConnectorRegistry

# ── Test connectors with capabilities ──


class ReaderConnector(BaseConnector):
    """Connector that only reads documents."""

    name: str = "Reader"
    connector_type: str = "reader"
    capabilities: List[ConnectorCapability] = [
        ConnectorCapability.DOCUMENT_READ,
        ConnectorCapability.FULL_SYNC,
    ]
    version: str = "2.0.0"
    features: List[str] = ["document"]

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


class FullFeatureConnector(BaseConnector):
    """Connector with all capabilities."""

    name: str = "FullFeature"
    connector_type: str = "full_feature"
    capabilities: List[ConnectorCapability] = [
        ConnectorCapability.DOCUMENT_READ,
        ConnectorCapability.DOCUMENT_WRITE,
        ConnectorCapability.SEARCH,
        ConnectorCapability.WEBHOOK,
        ConnectorCapability.INCREMENTAL_SYNC,
        ConnectorCapability.FULL_SYNC,
    ]
    version: str = "3.1.0"

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


class TestRegistryEnterprise:
    """Tests for the enterprise registry methods."""

    def setup_method(self) -> None:
        self.registry = ConnectorRegistry()

    def test_get_metadata(self) -> None:
        """Test get_metadata returns structured metadata."""
        self.registry.register("reader", ReaderConnector)
        meta = self.registry.get_metadata("reader")

        assert meta["name"] == "Reader"
        assert meta["type"] == "reader"
        assert meta["version"] == "2.0.0"
        assert "capabilities" in meta
        assert "document_read" in meta["capabilities"]
        assert "full_sync" in meta["capabilities"]
        assert "search" not in meta["capabilities"]

    def test_get_metadata_unknown_raises(self) -> None:
        """Test get_metadata raises for unknown type."""
        with pytest.raises(ValueError, match="Unknown connector type"):
            self.registry.get_metadata("nonexistent")

    def test_get_all_metadata(self) -> None:
        """Test get_all_metadata returns all entries."""
        self.registry.register("reader", ReaderConnector)
        self.registry.register("full_feature", FullFeatureConnector)
        all_meta = self.registry.get_all_metadata()

        assert "reader" in all_meta
        assert "full_feature" in all_meta
        assert all_meta["reader"]["version"] == "2.0.0"
        assert all_meta["full_feature"]["version"] == "3.1.0"

    def test_list_capabilities(self) -> None:
        """Test list_capabilities returns capability strings."""
        self.registry.register("full_feature", FullFeatureConnector)
        caps = self.registry.list_capabilities("full_feature")

        assert "document_read" in caps
        assert "document_write" in caps
        assert "search" in caps
        assert "webhook" in caps
        assert "incremental_sync" in caps

    def test_list_capabilities_unknown_raises(self) -> None:
        """Test list_capabilities raises for unknown type."""
        with pytest.raises(ValueError, match="Unknown connector type"):
            self.registry.list_capabilities("nonexistent")

    def test_get_version(self) -> None:
        """Test get_version returns semver string."""
        self.registry.register("reader", ReaderConnector)
        ver = self.registry.get_version("reader")
        assert ver == "2.0.0"

    def test_get_version_default(self) -> None:
        """Test get_version returns default when class has no version."""
        self.registry.register("reader", ReaderConnector)

        # Create a class without version attr
        class NoVersionConnector(BaseConnector):
            name: str = "NoVer"
            connector_type: str = "nover"

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

        self.registry.register("nover", NoVersionConnector)
        assert self.registry.get_version("nover") == "0.1.0"

    def test_check_support(self) -> None:
        """Test check_support returns correct boolean."""
        self.registry.register("reader", ReaderConnector)
        self.registry.register("full_feature", FullFeatureConnector)

        assert self.registry.check_support("reader", "document_read") is True
        assert self.registry.check_support("reader", "search") is False
        assert self.registry.check_support("full_feature", "webhook") is True
        assert self.registry.check_support("full_feature", "incremental_sync") is True

    def test_check_support_with_enum(self) -> None:
        """Test check_support with ConnectorCapability enum value."""
        self.registry.register("reader", ReaderConnector)
        assert self.registry.check_support("reader", ConnectorCapability.DOCUMENT_READ) is True
        assert self.registry.check_support("reader", ConnectorCapability.SEARCH) is False

    def test_discover(self) -> None:
        """Test discover finds connectors by capability."""
        self.registry.register("reader", ReaderConnector)
        self.registry.register("full_feature", FullFeatureConnector)

        readers = self.registry.discover("document_read")
        assert "reader" in readers
        assert "full_feature" in readers

        webhook_connectors = self.registry.discover("webhook")
        assert "reader" not in webhook_connectors
        assert "full_feature" in webhook_connectors

    def test_discover_with_enum(self) -> None:
        """Test discover with ConnectorCapability enum."""
        self.registry.register("reader", ReaderConnector)
        results = self.registry.discover(ConnectorCapability.DOCUMENT_READ)
        assert "reader" in results

"""Tests for connector health check functionality."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock

import pytest

from app.connector.base import BaseConnector, ConnectorDocument


class HealthyConnector(BaseConnector):
    """A connector that reports healthy."""
    name: str = "Healthy"
    connector_type: str = "healthy"

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

    async def health_check(self) -> Dict[str, Any]:
        return {
            "status": "healthy",
            "latency_ms": 45,
            "details": {"version": "1.0", "uptime": "120s"},
        }


class UnhealthyConnector(BaseConnector):
    """A connector that reports unhealthy."""
    name: str = "Unhealthy"
    connector_type: str = "unhealthy"

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

    async def health_check(self) -> Dict[str, Any]:
        return {
            "status": "unhealthy",
            "latency_ms": 0,
            "details": {"error": "Connection refused"},
        }


class WarningConnector(BaseConnector):
    """A connector that reports warning."""
    name: str = "Warning"
    connector_type: str = "warning"

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

    async def health_check(self) -> Dict[str, Any]:
        return {
            "status": "warning",
            "latency_ms": 250,
            "details": {"message": "High latency detected"},
        }


class DefaultHealthConnector(BaseConnector):
    """A connector using default health_check."""
    name: str = "Default"
    connector_type: str = "default"

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


class TestHealthCheck:
    """Tests for connector health checks."""

    async def test_healthy(self) -> None:
        """Test healthy status."""
        conn = HealthyConnector()
        result = await conn.health_check()
        assert result["status"] == "healthy"
        assert result["latency_ms"] == 45
        assert "version" in result["details"]

    async def test_unhealthy(self) -> None:
        """Test unhealthy status."""
        conn = UnhealthyConnector()
        result = await conn.health_check()
        assert result["status"] == "unhealthy"
        assert "Connection refused" in result["details"]["error"]

    async def test_warning(self) -> None:
        """Test warning status."""
        conn = WarningConnector()
        result = await conn.health_check()
        assert result["status"] == "warning"
        assert result["latency_ms"] == 250

    async def test_default_health_check(self) -> None:
        """Test the default health check returns 'unknown'."""
        conn = DefaultHealthConnector()
        result = await conn.health_check()
        assert result["status"] == "unknown"
        assert result["latency_ms"] == 0
        assert result["details"] == {}

    async def test_health_integration(self) -> None:
        """Test health check returns correct structure."""
        conn = HealthyConnector()
        result = await conn.health_check()

        # Must have all required keys
        assert "status" in result
        assert "latency_ms" in result
        assert "details" in result
        assert result["status"] in ("healthy", "warning", "unhealthy", "unknown")
"""Tests for connector API endpoints."""

from __future__ import annotations

from typing import Any, Dict
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import AsyncClient

from app.main import app as fastapi_app


class TestConnectorAPI:
    """Tests for /api/connectors endpoints."""

    @pytest_asyncio.fixture
    async def client(self, api_client) -> AsyncClient:
        """Use the shared api_client fixture from conftest."""
        return api_client

    async def test_list_connector_types(self, client: AsyncClient) -> None:
        """Test GET /api/connectors/types returns registered types."""
        resp = await client.get("/api/connectors/types")
        # Without auth, should return 401
        assert resp.status_code in (200, 401)
        if resp.status_code == 200:
            data = resp.json()
            assert "types" in data
            assert "feishu" in data["types"]
            assert "yuque" in data["types"]
            assert "gitlab" in data["types"]

    async def test_create_connector_no_auth(self, client: AsyncClient) -> None:
        """Test POST /api/connectors returns 401 without auth."""
        resp = await client.post(
            "/api/connectors/",
            json={"name": "Test", "type": "feishu"},
        )
        # All connector endpoints require permission, so 401 when no JWT
        assert resp.status_code == 401

    async def test_list_connectors_no_auth(self, client: AsyncClient) -> None:
        """Test GET /api/connectors returns 401 without auth."""
        resp = await client.get("/api/connectors/")
        assert resp.status_code == 401

    async def test_get_connector_no_auth(self, client: AsyncClient) -> None:
        """Test GET /api/connectors/{id} returns 401 without auth."""
        resp = await client.get("/api/connectors/nonexistent")
        assert resp.status_code == 401

    async def test_delete_connector_no_auth(self, client: AsyncClient) -> None:
        """Test DELETE /api/connectors/{id} returns 401 without auth."""
        resp = await client.delete("/api/connectors/nonexistent")
        assert resp.status_code == 401

    async def test_trigger_sync_no_auth(self, client: AsyncClient) -> None:
        """Test POST /api/connectors/{id}/sync returns 401 without auth."""
        resp = await client.post("/api/connectors/nonexistent/sync")
        assert resp.status_code == 401

    async def test_get_sync_status_no_auth(self, client: AsyncClient) -> None:
        """Test GET /api/connectors/{id}/status returns 401 without auth."""
        resp = await client.get("/api/connectors/nonexistent/status")
        assert resp.status_code == 401

    async def test_test_connection_no_auth(self, client: AsyncClient) -> None:
        """Test POST /api/connectors/{id}/test returns 401 without auth."""
        resp = await client.post("/api/connectors/nonexistent/test")
        assert resp.status_code == 401

    async def test_update_connector_no_auth(self, client: AsyncClient) -> None:
        """Test PUT /api/connectors/{id} returns 401 without auth."""
        resp = await client.put(
            "/api/connectors/nonexistent",
            json={"name": "Updated"},
        )
        assert resp.status_code == 401


class TestConnectorModels:
    """Tests for connector model enums and defaults."""

    def test_connector_type_enum(self) -> None:
        """Test ConnectorType enum values."""
        from app.connector.models import ConnectorType

        assert ConnectorType.FEISHU.value == "feishu"
        assert ConnectorType.YUQUE.value == "yuque"
        assert ConnectorType.GITLAB.value == "gitlab"
        assert ConnectorType.CONFLUENCE.value == "confluence"
        assert ConnectorType.JIRA.value == "jira"

    def test_sync_status_enum(self) -> None:
        """Test SyncStatus enum values."""
        from app.connector.models import SyncStatus

        assert SyncStatus.PENDING.value == "pending"
        assert SyncStatus.RUNNING.value == "running"
        assert SyncStatus.SUCCESS.value == "success"
        assert SyncStatus.FAILED.value == "failed"

    def test_connector_init_no_config(self) -> None:
        """Test BaseConnector subclass init with no config."""
        from app.connector.base import BaseConnector
        from app.connector.feishu import FeishuConnector

        assert FeishuConnector.name == "Feishu"
        assert FeishuConnector.connector_type == "feishu"

    def test_connector_document_to_dict_fields(self) -> None:
        """Test ConnectorDocument to_dict completeness."""
        from app.connector.base import ConnectorDocument

        doc = ConnectorDocument(
            id="test-id",
            title="Test",
            content="# Hello",
            url="https://example.com",
            metadata={"key": "value"},
        )
        d = doc.to_dict()
        assert set(d.keys()) == {"id", "title", "content", "url", "updated_at", "metadata"}
        assert d["id"] == "test-id"
        assert d["metadata"]["key"] == "value"
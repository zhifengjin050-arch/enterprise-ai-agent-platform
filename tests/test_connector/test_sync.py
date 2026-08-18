"""Tests for sync integration: repository, scheduler."""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.connector.base import BaseConnector, ConnectorDocument
from app.connector.models import ConnectorConfig, SyncRecord
from app.connector.repository import ConnectorConfigRepository, SyncRecordRepository
from app.connector.scheduler import SyncScheduler


class TestConnectorConfigRepository:
    """Tests for ConnectorConfigRepository."""

    async def test_create_connector(self, db_session: AsyncSession) -> None:
        """Test creating a connector config via repository."""
        repo = ConnectorConfigRepository(db_session)
        config = await repo.create(
            tenant_id="tenant-1",
            name="Test Connector",
            connector_type="feishu",
            config_json={"app_id": "test"},
            enabled=True,
        )
        assert config.id is not None
        assert config.name == "Test Connector"
        assert config.type == "feishu"

    async def test_get_connector(self, db_session: AsyncSession) -> None:
        """Test getting a connector by ID."""
        repo = ConnectorConfigRepository(db_session)
        created = await repo.create(name="Get Test", connector_type="yuque")
        fetched = await repo.get(created.id)
        assert fetched is not None
        assert fetched.id == created.id
        assert fetched.name == "Get Test"

    async def test_get_not_found(self, db_session: AsyncSession) -> None:
        """Test get returns None for missing ID."""
        repo = ConnectorConfigRepository(db_session)
        result = await repo.get("nonexistent-id")
        assert result is None

    async def test_list_connectors(self, db_session: AsyncSession) -> None:
        """Test listing connectors."""
        repo = ConnectorConfigRepository(db_session)
        await repo.create(name="C1", connector_type="feishu")
        await repo.create(name="C2", connector_type="yuque")
        await repo.create(name="C3", connector_type="gitlab")

        all_c = await repo.list()
        assert len(all_c) == 3

    async def test_list_with_type_filter(self, db_session: AsyncSession) -> None:
        """Test listing with type filter."""
        repo = ConnectorConfigRepository(db_session)
        await repo.create(name="C1", connector_type="feishu")
        await repo.create(name="C2", connector_type="yuque")

        feishu_list = await repo.list(connector_type="feishu")
        assert len(feishu_list) == 1
        assert feishu_list[0].name == "C1"

    async def test_list_enabled_only(self, db_session: AsyncSession) -> None:
        """Test listing only enabled connectors."""
        repo = ConnectorConfigRepository(db_session)
        await repo.create(name="Enabled", connector_type="feishu", enabled=True)
        await repo.create(name="Disabled", connector_type="yuque", enabled=False)

        enabled = await repo.list(enabled_only=True)
        assert len(enabled) == 1
        assert enabled[0].name == "Enabled"

    async def test_update_connector(self, db_session: AsyncSession) -> None:
        """Test updating a connector."""
        repo = ConnectorConfigRepository(db_session)
        created = await repo.create(name="Original", connector_type="feishu")
        updated = await repo.update(created.id, name="Updated", enabled=False)
        assert updated is not None
        assert updated.name == "Updated"
        assert updated.enabled is False

    async def test_update_not_found(self, db_session: AsyncSession) -> None:
        """Test update returns None for missing ID."""
        repo = ConnectorConfigRepository(db_session)
        result = await repo.update("missing", name="Nope")
        assert result is None

    async def test_delete_connector(self, db_session: AsyncSession) -> None:
        """Test deleting a connector."""
        repo = ConnectorConfigRepository(db_session)
        created = await repo.create(name="Delete Me", connector_type="feishu")
        deleted = await repo.delete(created.id)
        assert deleted is True
        fetched = await repo.get(created.id)
        assert fetched is None

    async def test_delete_not_found(self, db_session: AsyncSession) -> None:
        """Test delete returns False for missing ID."""
        repo = ConnectorConfigRepository(db_session)
        result = await repo.delete("missing")
        assert result is False

    async def test_update_last_sync(self, db_session: AsyncSession) -> None:
        """Test updating last_sync_at."""
        repo = ConnectorConfigRepository(db_session)
        created = await repo.create(name="Sync Test", connector_type="feishu")
        assert created.last_sync_at is None

        now_aware = datetime.now(timezone.utc)
        # Pass a naive datetime since SQLite stores timezone-aware columns as naive
        now_naive = now_aware.replace(tzinfo=None)
        await repo.update_last_sync(created.id, now_naive)
        await db_session.flush()
        await db_session.refresh(created)
        assert created.last_sync_at is not None
        # SQLite returns timezone-naive; ensure we can compare
        if created.last_sync_at.tzinfo is not None:
            assert (created.last_sync_at - now_aware).total_seconds() < 2
        else:
            # created.last_sync_at is naive, so make it aware for comparison
            last_sync_aware = created.last_sync_at.replace(tzinfo=timezone.utc)
            assert (last_sync_aware - now_aware).total_seconds() < 2


class TestSyncRecordRepository:
    """Tests for SyncRecordRepository."""

    async def test_create_record(self, db_session: AsyncSession) -> None:
        """Test creating a sync record."""
        repo = SyncRecordRepository(db_session)
        record = await repo.create(connector_id="conn-1", document_id="doc-1")
        assert record.id is not None
        assert record.connector_id == "conn-1"
        assert record.document_id == "doc-1"
        assert record.status == "pending"

    async def test_get_record(self, db_session: AsyncSession) -> None:
        """Test getting a sync record by ID."""
        repo = SyncRecordRepository(db_session)
        created = await repo.create(connector_id="conn-1")
        fetched = await repo.get(created.id)
        assert fetched is not None
        assert fetched.connector_id == "conn-1"

    async def test_list_by_connector(self, db_session: AsyncSession) -> None:
        """Test listing records by connector."""
        repo = SyncRecordRepository(db_session)
        await repo.create(connector_id="conn-a")
        await repo.create(connector_id="conn-a")
        await repo.create(connector_id="conn-b")

        conn_a_records = await repo.list_by_connector("conn-a")
        assert len(conn_a_records) == 2

        conn_b_records = await repo.list_by_connector("conn-b")
        assert len(conn_b_records) == 1

    async def test_update_status_success(self, db_session: AsyncSession) -> None:
        """Test updating a record to success."""
        repo = SyncRecordRepository(db_session)
        created = await repo.create(connector_id="conn-1")
        updated = await repo.update_status(
            created.id,
            status="success",
            documents_count=5,
        )
        assert updated is not None
        assert updated.status == "success"
        assert updated.documents_count == 5
        assert updated.finished_at is not None

    async def test_update_status_failed(self, db_session: AsyncSession) -> None:
        """Test updating a record to failed."""
        repo = SyncRecordRepository(db_session)
        created = await repo.create(connector_id="conn-1")
        updated = await repo.update_status(
            created.id,
            status="failed",
            error="Something went wrong",
        )
        assert updated is not None
        assert updated.status == "failed"
        assert updated.error == "Something went wrong"
        assert updated.finished_at is not None


class TestSyncScheduler:
    """Tests for SyncScheduler (unit)."""

    def test_is_due_never_synced(self) -> None:
        """Test that a connector with no last_sync is due."""
        cfg = ConnectorConfig(
            name="Test", type="feishu", enabled=True, last_sync_at=None,
        )
        assert SyncScheduler._is_due(cfg) is True

    def test_is_due_hourly_due(self) -> None:
        """Test hourly schedule when overdue."""
        old = datetime.now(timezone.utc) - timedelta(hours=2)
        cfg = ConnectorConfig(
            name="Test", type="feishu", enabled=True, last_sync_at=old,
            config_json={"schedule": "hourly"},
        )
        assert SyncScheduler._is_due(cfg) is True

    def test_is_due_hourly_not_due(self) -> None:
        """Test hourly schedule when not yet due."""
        recent = datetime.now(timezone.utc) - timedelta(minutes=30)
        cfg = ConnectorConfig(
            name="Test", type="feishu", enabled=True, last_sync_at=recent,
            config_json={"schedule": "hourly"},
        )
        assert SyncScheduler._is_due(cfg) is False

    def test_is_due_daily_due(self) -> None:
        """Test daily schedule when overdue."""
        old = datetime.now(timezone.utc) - timedelta(days=2)
        cfg = ConnectorConfig(
            name="Test", type="yuque", enabled=True, last_sync_at=old,
            config_json={"schedule": "daily"},
        )
        assert SyncScheduler._is_due(cfg) is True

    def test_is_due_daily_not_due(self) -> None:
        """Test daily schedule when not yet due."""
        recent = datetime.now(timezone.utc) - timedelta(hours=12)
        cfg = ConnectorConfig(
            name="Test", type="yuque", enabled=True, last_sync_at=recent,
            config_json={"schedule": "daily"},
        )
        assert SyncScheduler._is_due(cfg) is False

    def test_is_due_never(self) -> None:
        """Test never schedule."""
        old = datetime.now(timezone.utc) - timedelta(days=30)
        cfg = ConnectorConfig(
            name="Test", type="feishu", enabled=True, last_sync_at=old,
            config_json={"schedule": "never"},
        )
        assert SyncScheduler._is_due(cfg) is False

    def test_is_due_custom_interval(self) -> None:
        """Test custom interval minutes."""
        old = datetime.now(timezone.utc) - timedelta(minutes=30)
        cfg = ConnectorConfig(
            name="Test", type="feishu", enabled=True, last_sync_at=old,
            config_json={"schedule_interval_minutes": 15},
        )
        assert SyncScheduler._is_due(cfg) is True
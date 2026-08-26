"""Tests for ConnectorConfig and SyncRecord ORM models."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.connector.models import ConnectorConfig, SyncRecord


class TestConnectorConfigModel:
    """Tests for ConnectorConfig ORM model."""

    async def test_create_connector_config(self, db_session: AsyncSession) -> None:
        """Test creating a ConnectorConfig record."""
        config = ConnectorConfig(
            name="Test Feishu",
            type="feishu",
            config_json={"app_id": "test"},
            enabled=True,
        )
        db_session.add(config)
        await db_session.flush()
        await db_session.refresh(config)

        assert config.id is not None
        assert len(str(config.id)) == 36  # UUID length
        assert config.name == "Test Feishu"
        assert config.type == "feishu"
        assert config.config_json == {"app_id": "test"}
        assert config.enabled is True
        assert config.created_at is not None

    async def test_connector_config_defaults(self, db_session: AsyncSession) -> None:
        """Test default values."""
        config = ConnectorConfig(name="Default Test", type="yuque")
        db_session.add(config)
        await db_session.flush()
        await db_session.refresh(config)

        assert config.enabled is True
        assert config.config_json is None
        assert config.last_sync_at is None

    async def test_connector_config_to_dict(self, db_session: AsyncSession) -> None:
        """Test to_dict serialization."""
        config = ConnectorConfig(
            name="Serialize Test",
            type="gitlab",
            config_json={"url": "https://gitlab.com", "token": "abc"},
        )
        db_session.add(config)
        await db_session.flush()
        await db_session.refresh(config)

        d = config.to_dict()
        assert d["name"] == "Serialize Test"
        assert d["type"] == "gitlab"
        assert d["enabled"] is True
        assert "id" in d
        assert "created_at" in d


class TestSyncRecordModel:
    """Tests for SyncRecord ORM model."""

    async def test_create_sync_record(self, db_session: AsyncSession) -> None:
        """Test creating a SyncRecord."""
        record = SyncRecord(
            connector_id="test-connector-id",
            document_id="doc-123",
            status="pending",
        )
        db_session.add(record)
        await db_session.flush()
        await db_session.refresh(record)

        assert record.id is not None
        assert len(str(record.id)) == 36
        assert record.connector_id == "test-connector-id"
        assert record.document_id == "doc-123"
        assert record.status == "pending"
        assert record.started_at is not None
        assert record.finished_at is None

    async def test_sync_record_defaults(self, db_session: AsyncSession) -> None:
        """Test SyncRecord default status."""
        record = SyncRecord(connector_id="conn-1")
        db_session.add(record)
        await db_session.flush()
        await db_session.refresh(record)

        assert record.status == "pending"
        assert record.error is None
        assert record.documents_count is None
        assert record.started_at is not None

    async def test_sync_record_to_dict(self, db_session: AsyncSession) -> None:
        """Test to_dict serialization."""
        record = SyncRecord(
            connector_id="test-conn",
            status="success",
            documents_count=5,
        )
        db_session.add(record)
        await db_session.flush()
        await db_session.refresh(record)

        d = record.to_dict()
        assert d["connector_id"] == "test-conn"
        assert d["status"] == "success"
        assert d["documents_count"] == 5
        assert "id" in d
        assert "started_at" in d

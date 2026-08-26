"""Tests for the ConnectorCapability enum and capability declarations."""

from __future__ import annotations

from app.connector.capability import ConnectorCapability


class TestConnectorCapability:
    """Tests for the ConnectorCapability enum."""

    def test_enum_values(self) -> None:
        """Test all enum values."""
        assert ConnectorCapability.DOCUMENT_READ.value == "document_read"
        assert ConnectorCapability.DOCUMENT_WRITE.value == "document_write"
        assert ConnectorCapability.SEARCH.value == "search"
        assert ConnectorCapability.WEBHOOK.value == "webhook"
        assert ConnectorCapability.INCREMENTAL_SYNC.value == "incremental_sync"
        assert ConnectorCapability.FULL_SYNC.value == "full_sync"

    def test_unique_values(self) -> None:
        """Test that all values are unique."""
        values = [c.value for c in ConnectorCapability]
        assert len(values) == len(set(values))

    def test_feishu_capabilities(self) -> None:
        """Test Feishu connector declares correct capabilities."""
        from app.connector.feishu import FeishuConnector

        caps = [c.value for c in FeishuConnector.capabilities]
        assert "document_read" in caps
        assert "search" in caps
        assert "full_sync" in caps
        assert "incremental_sync" in caps
        assert "webhook" not in caps

    def test_yuque_capabilities(self) -> None:
        """Test Yuque connector declares correct capabilities."""
        from app.connector.yuque import YuqueConnector

        caps = [c.value for c in YuqueConnector.capabilities]
        assert "document_read" in caps
        assert "full_sync" in caps

    def test_gitlab_capabilities(self) -> None:
        """Test GitLab connector declares correct capabilities."""
        from app.connector.gitlab import GitLabConnector

        caps = [c.value for c in GitLabConnector.capabilities]
        assert "document_read" in caps
        assert "webhook" in caps
        assert "full_sync" in caps
        assert "search" not in caps

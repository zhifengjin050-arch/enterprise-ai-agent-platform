"""Tests for connector configuration schemas and validation."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.connector.config_schemas import (
    CONNECTOR_CONFIG_SCHEMAS,
    BaseConnectorConfig,
    FeishuConfig,
    GitLabConfig,
    YuqueConfig,
    validate_connector_config,
)
from app.core.exceptions import ConnectorConfigError


class TestFeishuConfig:
    """Tests for Feishu configuration schema."""

    def test_valid_config(self) -> None:
        """Test valid Feishu config."""
        config = FeishuConfig(
            app_id="cli_abc123",
            app_secret="secret_key_here",
        )
        assert config.app_id == "cli_abc123"
        assert config.app_secret == "secret_key_here"
        assert config.tenant_key is None

    def test_valid_config_with_optional(self) -> None:
        """Test valid Feishu config with optional fields."""
        config = FeishuConfig(
            app_id="cli_abc",
            app_secret="secret",
            tenant_key="tenant_token",
        )
        assert config.tenant_key == "tenant_token"

    def test_missing_app_id(self) -> None:
        """Test missing required field raises."""
        with pytest.raises(ValidationError):
            FeishuConfig(app_secret="secret")

    def test_missing_app_secret(self) -> None:
        """Test missing app_secret raises."""
        with pytest.raises(ValidationError):
            FeishuConfig(app_id="cli_abc")

    def test_empty_strings(self) -> None:
        """Test empty strings raise validation error."""
        with pytest.raises(ValidationError):
            FeishuConfig(app_id="", app_secret="secret")
        with pytest.raises(ValidationError):
            FeishuConfig(app_id="cli_abc", app_secret="")


class TestYuqueConfig:
    """Tests for Yuque configuration schema."""

    def test_valid_config(self) -> None:
        """Test valid Yuque config."""
        config = YuqueConfig(token="yuque_token_123")
        assert config.token == "yuque_token_123"
        assert config.base_url is None
        assert config.namespace is None

    def test_valid_config_with_options(self) -> None:
        """Test valid Yuque config with optional fields."""
        config = YuqueConfig(
            token="token",
            base_url="https://custom.yuque.com/api/v2",
            namespace="org/repo",
        )
        assert config.base_url == "https://custom.yuque.com/api/v2"
        assert config.namespace == "org/repo"

    def test_missing_token(self) -> None:
        """Test missing token raises."""
        with pytest.raises(ValidationError):
            YuqueConfig()


class TestGitLabConfig:
    """Tests for GitLab configuration schema."""

    def test_valid_config(self) -> None:
        """Test valid GitLab config."""
        config = GitLabConfig(
            url="https://gitlab.com",
            token="glpat-xyz",
            project_id="12345",
        )
        assert config.url == "https://gitlab.com"
        assert config.token == "glpat-xyz"
        assert config.project_id == "12345"

    def test_defaults(self) -> None:
        """Test default values for optional fields."""
        config = GitLabConfig(
            url="https://gitlab.example.com",
            token="token",
            project_id="42",
        )
        assert config.wiki_enabled is True
        assert config.readme_enabled is True

    def test_url_validation(self) -> None:
        """Test URL validation."""
        with pytest.raises(ValidationError, match="must start with http"):
            GitLabConfig(
                url="ftp://gitlab.com",
                token="token",
                project_id="1",
            )

    def test_url_strips_trailing_slash(self) -> None:
        """Test trailing slash is stripped."""
        config = GitLabConfig(
            url="https://gitlab.com/",
            token="token",
            project_id="1",
        )
        assert config.url == "https://gitlab.com"

    def test_missing_required(self) -> None:
        """Test missing required fields raise."""
        with pytest.raises(ValidationError):
            GitLabConfig(token="token", project_id="1")
        with pytest.raises(ValidationError):
            GitLabConfig(url="https://gitlab.com", project_id="1")
        with pytest.raises(ValidationError):
            GitLabConfig(url="https://gitlab.com", token="token")


class TestBaseConnectorConfig:
    """Tests for the generic fallback config."""

    def test_empty_config(self) -> None:
        """Test empty config defaults to empty dict."""
        config = BaseConnectorConfig()
        assert config.config == {}

    def test_with_config(self) -> None:
        """Test config with arbitrary data."""
        config = BaseConnectorConfig(config={"custom_field": "value"})
        assert config.config["custom_field"] == "value"


class TestConfigSchemaRegistry:
    """Tests for CONNECTOR_CONFIG_SCHEMAS registry."""

    def test_schemas_registered(self) -> None:
        """Test all expected schemas are registered."""
        assert "feishu" in CONNECTOR_CONFIG_SCHEMAS
        assert "yuque" in CONNECTOR_CONFIG_SCHEMAS
        assert "gitlab" in CONNECTOR_CONFIG_SCHEMAS
        assert CONNECTOR_CONFIG_SCHEMAS["feishu"] == FeishuConfig
        assert CONNECTOR_CONFIG_SCHEMAS["yuque"] == YuqueConfig
        assert CONNECTOR_CONFIG_SCHEMAS["gitlab"] == GitLabConfig

    def test_validate_connector_config_valid(self) -> None:
        """Test validate_connector_config with valid data."""
        result = validate_connector_config(
            "feishu",
            {"app_id": "cli_abc", "app_secret": "secret"},
        )
        assert result["app_id"] == "cli_abc"
        assert result["app_secret"] == "secret"

    def test_validate_connector_config_invalid(self) -> None:
        """Test validate_connector_config raises on invalid data."""
        with pytest.raises(ConnectorConfigError, match="Invalid configuration"):
            validate_connector_config(
                "feishu",
                {"app_id": ""},  # Missing app_secret, empty app_id
            )

    def test_validate_connector_config_no_schema(self) -> None:
        """Test validate_connector_config with no schema falls through."""
        result = validate_connector_config(
            "unknown_type",
            {"some": "data"},
        )
        assert result == {"some": "data"}

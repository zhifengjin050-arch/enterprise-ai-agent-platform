"""Pydantic configuration schemas for each connector type.

Provides validation of connector-specific configuration before the
connector is initialised.  Each schema class defines the required and
optional fields for a given external knowledge source.

Schemas:
    FeishuConfig:  app_id, app_secret, tenant_key
    YuqueConfig:   token, base_url, namespace
    GitLabConfig:  url, token, project_id, wiki_enabled, readme_enabled
    BaseConnectorConfig:  generic dict-based fallback
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, field_validator


class FeishuConfig(BaseModel):
    """Configuration schema for Feishu/Lark Cloud Document connector.

    Attributes:
        app_id: Feishu Open App ID.
        app_secret: Feishu Open App Secret.
        tenant_key: Optional tenant access token for tenant-level access.
    """

    app_id: str = Field(..., min_length=1, description="Feishu Open App ID")
    app_secret: str = Field(..., min_length=1, description="Feishu Open App Secret")
    tenant_key: Optional[str] = Field(None, description="Tenant access token")


class YuqueConfig(BaseModel):
    """Configuration schema for Yuque (语雀) connector.

    Attributes:
        token: Yuque personal access token.
        base_url: Optional custom API base URL.
        namespace: Optional specific namespace to sync (e.g., "org/repo").
    """

    token: str = Field(..., min_length=1, description="Yuque API token")
    base_url: Optional[str] = Field(
        None,
        description="Custom base URL (default: https://www.yuque.com/api/v2)",
    )
    namespace: Optional[str] = Field(
        None,
        description="Specific namespace to sync (e.g., 'org/repo')",
    )


class GitLabConfig(BaseModel):
    """Configuration schema for GitLab Wiki connector.

    Attributes:
        url: GitLab instance URL (e.g., "https://gitlab.com").
        token: GitLab Personal Access Token.
        project_id: The GitLab project ID (numeric).
        wiki_enabled: Whether to sync Wiki pages (default: True).
        readme_enabled: Whether to sync the project README (default: True).
    """

    url: str = Field(..., min_length=1, description="GitLab instance URL")
    token: str = Field(..., min_length=1, description="GitLab Personal Access Token")
    project_id: str = Field(..., min_length=1, description="GitLab project ID (numeric)")

    wiki_enabled: bool = Field(True, description="Sync Wiki pages")
    readme_enabled: bool = Field(True, description="Sync project README")

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        """Ensure the URL starts with http:// or https://."""
        if not v.startswith(("http://", "https://")):
            msg = f"GitLab URL must start with http:// or https://, got '{v}'"
            raise ValueError(msg)
        return v.rstrip("/")


class BaseConnectorConfig(BaseModel):
    """Generic dict-based fallback config for ad-hoc connector types."""

    config: Dict[str, Any] = Field(default_factory=dict, description="Raw config dict")


# ── Schema registry ──

CONNECTOR_CONFIG_SCHEMAS: Dict[str, type[BaseModel]] = {
    "feishu": FeishuConfig,
    "yuque": YuqueConfig,
    "gitlab": GitLabConfig,
}


def validate_connector_config(
    connector_type: str,
    config: Dict[str, Any],
) -> Dict[str, Any]:
    """Validate a connector's configuration against its schema.

    Args:
        connector_type: The connector type key (e.g., "feishu").
        config: Raw configuration dict to validate.

    Returns:
        The validated config dict (with defaults filled in).

    Raises:
        ConnectorConfigError: If validation fails.
    """
    from app.core.exceptions import ConnectorConfigError

    schema_cls = CONNECTOR_CONFIG_SCHEMAS.get(connector_type)
    if schema_cls is None:
        # No schema registered — trust the config as-is
        return config

    try:
        validated = schema_cls(**config)
        return validated.model_dump()
    except Exception as exc:
        raise ConnectorConfigError(
            message=f"Invalid configuration for connector type '{connector_type}': {exc}",
            details={"connector_type": connector_type, "validation_error": str(exc)},
        ) from exc

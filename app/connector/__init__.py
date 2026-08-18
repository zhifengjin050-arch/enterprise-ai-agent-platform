"""Enterprise Knowledge Connector Layer.

Provides an extensible adapter framework for synchronizing documents
from external knowledge sources (Feishu, Yuque, GitLab, Confluence, Jira)
into the Enterprise AI Knowledge Copilot document pipeline.

Architecture:
    BaseConnector (abstract) -> FeishuConnector, YuqueConnector, GitLabConnector
    ConnectorRegistry -> factory for creating connector instances
    ConnectorLifecycleManager -> state machine for connector lifecycle
    ConnectorFactory -> high-level create-and-initialise helper
    Scheduler -> periodic sync orchestration

New in v0.7.0:
    - Connector lifecycle management (REGISTERED → INITIALIZING → READY → ...)
    - Connector capability system (DOCUMENT_READ, SEARCH, WEBHOOK, etc.)
    - Connector metadata / version management
    - Pydantic config validation schemas (FeishuConfig, YuqueConfig, GitLabConfig)
    - Retry policy with exponential backoff
    - Full / Incremental / Delta sync modes
    - Health check API at GET /api/connectors/{id}/health
"""
from app.connector.base import BaseConnector, ConnectorDocument, ConnectorMetadata
from app.connector.capability import ConnectorCapability
from app.connector.config_schemas import (
    CONNECTOR_CONFIG_SCHEMAS,
    BaseConnectorConfig,
    FeishuConfig,
    GitLabConfig,
    YuqueConfig,
    validate_connector_config,
)
from app.connector.exceptions import (
    AuthenticationError,
    ConnectionError,
    ConnectorError,
    NotFoundError,
    SyncError,
)
from app.connector.factory import ConnectorFactory, connector_factory

# Register built-in connectors
from app.connector.feishu import FeishuConnector
from app.connector.gitlab import GitLabConnector
from app.connector.lifecycle import (
    ConnectorLifecycleManager,
    ConnectorState,
    lifecycle_manager,
)
from app.connector.models import ConnectorConfig, SyncRecord
from app.connector.registry import ConnectorRegistry, connector_registry
from app.connector.retry import ConnectorRetryPolicy, default_retry_policy, is_retryable
from app.connector.sync_modes import SyncCursor, SyncMode, SyncResult, normalize_sync_result
from app.connector.yuque import YuqueConnector

connector_registry.register("feishu", FeishuConnector)
connector_registry.register("yuque", YuqueConnector)
connector_registry.register("gitlab", GitLabConnector)

__all__ = [
    # Core
    "BaseConnector",
    "ConnectorDocument",
    "ConnectorMetadata",
    # Capability
    "ConnectorCapability",
    # Config schemas
    "FeishuConfig",
    "YuqueConfig",
    "GitLabConfig",
    "BaseConnectorConfig",
    "CONNECTOR_CONFIG_SCHEMAS",
    "validate_connector_config",
    # Exceptions
    "ConnectorError",
    "ConnectionError",
    "AuthenticationError",
    "NotFoundError",
    "SyncError",
    # Factory
    "ConnectorFactory",
    "connector_factory",
    # Lifecycle
    "ConnectorLifecycleManager",
    "ConnectorState",
    "lifecycle_manager",
    # Models
    "ConnectorConfig",
    "SyncRecord",
    # Registry
    "ConnectorRegistry",
    "connector_registry",
    # Retry
    "ConnectorRetryPolicy",
    "default_retry_policy",
    "is_retryable",
    # Sync modes
    "SyncMode",
    "SyncCursor",
    "SyncResult",
    "normalize_sync_result",
    # Connector implementations
    "FeishuConnector",
    "YuqueConnector",
    "GitLabConnector",
]

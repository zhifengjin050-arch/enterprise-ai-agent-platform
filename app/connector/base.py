"""Abstract base class for all external knowledge source connectors.

Defines the ConnectorDocument data transfer object and the BaseConnector
interface that all adapters must implement.

Features:
    - Lifecycle management (initialize / validate / health_check / cleanup)
    - Capability declaration
    - Version management
    - Structured metadata
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from app.connector.capability import ConnectorCapability

if TYPE_CHECKING:
    from app.connector.sync_modes import SyncResult


@dataclass
class ConnectorDocument:
    """Unified document format returned by all connectors.

    Attributes:
        id: External document ID from the source system.
        title: Document title.
        content: Document content (typically Markdown).
        url: URL to the original document in the source system.
        updated_at: Last modification timestamp from source.
        metadata: Optional key-value pairs (tags, author, source-specific data).
    """

    id: str = ""
    title: str = ""
    content: str = ""
    url: str = ""
    updated_at: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to a serializable dict."""
        return {
            "id": self.id,
            "title": self.title,
            "content": self.content,
            "url": self.url,
            "updated_at": self.updated_at or datetime.now(timezone.utc).isoformat(),
            "metadata": self.metadata,
        }


@dataclass
class ConnectorMetadata:
    """Structured metadata describing a connector and its capabilities.

    Attributes:
        name: Human-readable connector name (e.g., "Feishu").
        connector_type: Registered type key (e.g., "feishu").
        version: Connector adapter version (semver).
        author: Maintainer information.
        description: Short description of the connector's purpose.
        features: List of supported features (e.g., ["document", "wiki", "search"]).
        capabilities: List of declared ConnectorCapability values.
        config_schema: JSON Schema-like dict describing required config fields.
    """

    name: str = "unknown"
    connector_type: str = "unknown"
    version: str = "0.1.0"
    author: str = ""
    description: str = ""
    features: List[str] = field(default_factory=list)
    capabilities: List[ConnectorCapability] = field(default_factory=list)
    config_schema: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a plain dict for API responses."""
        return {
            "name": self.name,
            "type": self.connector_type,
            "version": self.version,
            "author": self.author,
            "description": self.description,
            "features": self.features,
            "capabilities": [c.value for c in self.capabilities],
            "config_schema": self.config_schema,
        }


class BaseConnector(ABC):
    """Abstract base class for external knowledge source connectors.

    All connector adapters must implement:
        - test_connection()
        - fetch_documents()
        - get_document()
        - sync()

    Connectors may override lifecycle hooks:
        - initialize()
        - validate_config()
        - health_check()
        - cleanup()

    Class-level attributes to set:
        - name: Human-readable name.
        - connector_type: Type key registered in the registry.
        - version: Semver string.
        - author: Maintainer identifier.
        - description: Short purpose description.
        - capabilities: List of ConnectorCapability values.
        - config_schema: Pydantic dict describing expected config fields.
    """

    # ── Identity & Metadata ──
    name: str = "unknown"
    connector_type: str = "unknown"
    version: str = "0.1.0"
    author: str = ""
    description: str = ""
    capabilities: List[ConnectorCapability] = []
    features: List[str] = []
    config_schema: Dict[str, Any] = {}

    def __init__(
        self,
        *,
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialize the connector with configuration.

        Args:
            config: Connector-specific configuration dict (API keys, tokens, etc.).
        """
        self._config: Dict[str, Any] = config or {}

    # ── Lifecycle Hooks (optional override) ──

    async def initialize(self) -> None:
        """Initialize the connector (e.g., create HTTP client, establish connection).

        Called once before the connector is used. Default is a no-op.
        """
        pass

    async def validate_config(self) -> bool:
        """Validate that the provided configuration is complete and well-formed.

        Override in subclasses to enforce required fields.

        Returns:
            True if configuration is valid.

        Raises:
            ConnectorConfigError: If required fields are missing or invalid.
        """
        # Default implementation — permissive; subclasses should override
        return True

    async def health_check(self) -> Dict[str, Any]:
        """Perform a health check against the external source.

        Returns:
            Dict with keys:
                - status: "healthy" | "warning" | "unhealthy"
                - latency_ms: Response time in milliseconds.
                - details: Optional diagnostic information.
        """
        return {"status": "unknown", "latency_ms": 0, "details": {}}

    async def cleanup(self) -> None:
        """Release resources held by the connector (HTTP clients, file handles, etc.).

        Called when the connector is being destroyed or disabled.
        Default is a no-op.
        """
        pass

    # ── Core Abstract Methods ──

    @abstractmethod
    async def test_connection(self) -> bool:
        """Test connectivity to the external knowledge source.

        Returns:
            True if the connection is successful.

        Raises:
            AuthenticationError: If credentials are invalid.
            ConnectionError: If the remote service is unreachable.
        """
        ...

    @abstractmethod
    async def fetch_documents(self) -> List[ConnectorDocument]:
        """Fetch a list of all available documents from the source.

        Returns:
            A list of ConnectorDocument instances (metadata only, no full content).

        Raises:
            ConnectionError: If the remote service is unreachable.
            AuthenticationError: If credentials are invalid.
        """
        ...

    @abstractmethod
    async def get_document(self, document_id: str) -> Optional[ConnectorDocument]:
        """Fetch a single document by its external ID, including full content.

        Args:
            document_id: The external document ID in the source system.

        Returns:
            A ConnectorDocument with full content, or None if not found.

        Raises:
            ConnectionError: If the remote service is unreachable.
        """
        ...

    @abstractmethod
    async def sync(
        self,
        sync_mode: str = "full",
        cursor: Optional[str] = None,
    ) -> "SyncResult":
        """Perform a sync: fetch documents with their content.

        Args:
            sync_mode: "full" (all documents) or "incremental" (since last cursor).
            cursor: Optional checkpoint cursor for incremental sync.

        Returns:
            A SyncResult with documents, next_cursor, and has_more.

        Note:
            For backward compatibility, returning List[ConnectorDocument] is
            still accepted by SyncEngine via normalize_sync_result().
            New connectors SHOULD return SyncResult.
        """
        ...

    # ── Metadata ──

    def get_metadata(self) -> Dict[str, Any]:
        """Return metadata about this connector instance.

        Returns:
            Dict with connector identity and capability information.
        """
        return ConnectorMetadata(
            name=self.name,
            connector_type=self.connector_type,
            version=self.version,
            author=self.author,
            description=self.description,
            features=self.features,
            capabilities=self.capabilities,
            config_schema=self.config_schema,
        ).to_dict()

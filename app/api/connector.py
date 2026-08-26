"""Connector API endpoints for managing external knowledge source connectors.

Provides CRUD operations for connector configurations and sync trigger/status.
Requires appropriate RBAC permissions (connector.read, connector.write, connector.sync).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user, require_permission
from app.connector.lifecycle import lifecycle_manager
from app.connector.registry import connector_registry
from app.connector.repository import ConnectorConfigRepository, SyncRecordRepository
from app.db.session import get_db
from app.sync_engine.worker import sync_worker

router = APIRouter(prefix="/api/connectors", tags=["Connectors"])


# ──────────────────────────────────────────────
# Pydantic request/response models
# ──────────────────────────────────────────────


class SyncTriggerRequest(BaseModel):
    """Optional body for sync trigger."""

    sync_mode: str = Field("full", description="full | incremental | delta")
    resume: bool = Field(True, description="Resume from checkpoint for incremental")


class ConnectorCreateRequest(BaseModel):
    """Request body for creating a connector."""

    name: str
    type: str
    config_json: Optional[Dict[str, Any]] = None
    enabled: bool = True


class ConnectorUpdateRequest(BaseModel):
    """Request body for updating a connector."""

    name: Optional[str] = None
    config_json: Optional[Dict[str, Any]] = None
    enabled: Optional[bool] = None


class ConnectorResponse(BaseModel):
    """Connector configuration response."""

    id: str
    tenant_id: Optional[str] = None
    name: str
    type: str
    enabled: bool
    last_sync_at: Optional[str] = None
    created_at: Optional[str] = None


class SyncRecordResponse(BaseModel):
    """Sync record response."""

    id: str
    connector_id: str
    document_id: Optional[str] = None
    status: str
    error: Optional[str] = None
    documents_count: Optional[int] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None


# ──────────────────────────────────────────────
# Endpoints
# ──────────────────────────────────────────────


@router.post("/")
async def create_connector(
    request: ConnectorCreateRequest,
    session: AsyncSession = Depends(get_db),
    _=Depends(require_permission("connector.write")),
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Create a new connector configuration.

    Args:
        request: Connector name, type, config.
        session: DB session.
        current_user: Authenticated user.

    Returns:
        Created connector config.
    """
    # Validate connector type is registered
    if not connector_registry.is_registered(request.type):
        available = list(connector_registry.list_types().keys())
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported connector type: '{request.type}'. Available: {available}",
        )

    repo = ConnectorConfigRepository(session)
    connector = await repo.create(
        tenant_id=current_user.get("tenant_id") if current_user else None,
        name=request.name,
        connector_type=request.type,
        config_json=request.config_json or {},
        enabled=request.enabled,
    )
    await session.commit()

    return {
        "id": connector.id,
        "tenant_id": connector.tenant_id,
        "name": connector.name,
        "type": connector.type,
        "enabled": connector.enabled,
        "last_sync_at": connector.last_sync_at.isoformat() if connector.last_sync_at else None,
        "created_at": connector.created_at.isoformat() if connector.created_at else None,
    }


@router.get("/")
async def list_connectors(
    type_filter: Optional[str] = Query(None, alias="type"),
    enabled_filter: Optional[bool] = Query(None, alias="enabled"),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db),
    _=Depends(require_permission("connector.read")),
) -> Dict[str, Any]:
    """List all connector configurations.

    Args:
        type_filter: Optional connector type filter.
        enabled_filter: Optional enabled filter.
        limit: Max results.
        offset: Pagination offset.
        session: DB session.

    Returns:
        Dict with connectors list and total count.
    """
    repo = ConnectorConfigRepository(session)
    connectors = await repo.list(
        connector_type=type_filter,
        limit=limit,
        offset=offset,
    )

    if enabled_filter is not None:
        connectors = [c for c in connectors if c.enabled == enabled_filter]

    return {
        "connectors": [
            {
                "id": c.id,
                "tenant_id": c.tenant_id,
                "name": c.name,
                "type": c.type,
                "enabled": c.enabled,
                "last_sync_at": c.last_sync_at.isoformat() if c.last_sync_at else None,
                "created_at": c.created_at.isoformat() if c.created_at else None,
            }
            for c in connectors
        ],
        "total": len(connectors),
    }


@router.get("/types")
async def list_connector_types(
    _=Depends(require_permission("connector.read")),
) -> Dict[str, Any]:
    """List all registered connector types.

    Returns:
        Dict with available types and their metadata.
    """
    return {
        "types": connector_registry.list_types(),
        "metadata": connector_registry.get_all_metadata(),
    }


@router.get("/{connector_id}")
async def get_connector(
    connector_id: str,
    session: AsyncSession = Depends(get_db),
    _=Depends(require_permission("connector.read")),
) -> Dict[str, Any]:
    """Get a connector configuration by ID.

    Args:
        connector_id: UUID string.
        session: DB session.

    Returns:
        Connector config details.
    """
    repo = ConnectorConfigRepository(session)
    connector = await repo.get(connector_id)
    if connector is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Connector '{connector_id}' not found",
        )
    return {
        "id": connector.id,
        "tenant_id": connector.tenant_id,
        "name": connector.name,
        "type": connector.type,
        "enabled": connector.enabled,
        "config_json": connector.config_json,
        "last_sync_at": connector.last_sync_at.isoformat() if connector.last_sync_at else None,
        "created_at": connector.created_at.isoformat() if connector.created_at else None,
        "updated_at": connector.updated_at.isoformat() if connector.updated_at else None,
    }


@router.put("/{connector_id}")
async def update_connector(
    connector_id: str,
    request: ConnectorUpdateRequest,
    session: AsyncSession = Depends(get_db),
    _=Depends(require_permission("connector.write")),
) -> Dict[str, Any]:
    """Update a connector configuration.

    Args:
        connector_id: UUID string.
        request: Fields to update.
        session: DB session.

    Returns:
        Updated connector config.
    """
    repo = ConnectorConfigRepository(session)
    connector = await repo.update(
        connector_id,
        name=request.name,
        config_json=request.config_json,
        enabled=request.enabled,
    )
    if connector is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Connector '{connector_id}' not found",
        )
    await session.commit()
    return {
        "id": connector.id,
        "name": connector.name,
        "type": connector.type,
        "enabled": connector.enabled,
        "last_sync_at": connector.last_sync_at.isoformat() if connector.last_sync_at else None,
    }


@router.delete("/{connector_id}")
async def delete_connector(
    connector_id: str,
    session: AsyncSession = Depends(get_db),
    _=Depends(require_permission("connector.write")),
) -> Dict[str, Any]:
    """Delete a connector configuration.

    Args:
        connector_id: UUID string.
        session: DB session.

    Returns:
        Confirmation message.
    """
    repo = ConnectorConfigRepository(session)
    deleted = await repo.delete(connector_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Connector '{connector_id}' not found",
        )
    await session.commit()
    return {"detail": f"Connector '{connector_id}' deleted"}


@router.post("/{connector_id}/sync")
async def trigger_sync(
    connector_id: str,
    request: Optional[SyncTriggerRequest] = None,
    session: AsyncSession = Depends(get_db),
    _=Depends(require_permission("connector.sync")),
) -> Dict[str, Any]:
    """Trigger an immediate sync for a connector via the Sync Engine.

    Creates a SyncJob and executes it in the background via SyncWorker.
    Also creates a legacy SyncRecord for backward compatibility.

    Args:
        connector_id: UUID string.
        request: Optional sync_mode and resume settings.
        session: DB session.

    Returns:
        Sync initiation status with sync_job_id.
    """
    repo = ConnectorConfigRepository(session)
    connector = await repo.get(connector_id)
    if connector is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Connector '{connector_id}' not found",
        )
    if not connector.enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Connector '{connector_id}' is disabled",
        )

    sync_mode = (request.sync_mode if request else None) or (
        (connector.config_json or {}).get("sync_mode", "full")
    )
    resume = request.resume if request else True

    # Legacy SyncRecord for backward compatibility
    sync_repo = SyncRecordRepository(session)
    record = await sync_repo.create(
        connector_id=connector_id,
        status="pending",
    )
    await session.commit()

    # Submit via SyncWorker (Enterprise Sync Engine)
    try:
        job_id = await sync_worker.submit(
            connector_id=connector_id,
            connector_type=connector.type,
            config=connector.config_json or {},
            sync_mode=sync_mode,
            tenant_id=connector.tenant_id,
            resume=resume,
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    return {
        "detail": f"Sync triggered for connector '{connector_id}'",
        "sync_job_id": job_id,
        "sync_record_id": record.id,  # backward compatible
        "sync_mode": sync_mode,
        "status": "pending",
    }


@router.get("/{connector_id}/status")
async def get_sync_status(
    connector_id: str,
    limit: int = Query(10, le=50),
    session: AsyncSession = Depends(get_db),
    _=Depends(require_permission("connector.read")),
) -> Dict[str, Any]:
    """Get sync status/history for a connector.

    Args:
        connector_id: UUID string.
        limit: Max sync records.
        session: DB session.

    Returns:
        Dict with recent sync records.
    """
    sync_repo = SyncRecordRepository(session)
    records = await sync_repo.list_by_connector(connector_id, limit=limit)
    return {
        "connector_id": connector_id,
        "sync_records": [
            {
                "id": r.id,
                "status": r.status,
                "error": r.error,
                "documents_count": r.documents_count,
                "started_at": r.started_at.isoformat() if r.started_at else None,
                "finished_at": r.finished_at.isoformat() if r.finished_at else None,
            }
            for r in records
        ],
        "total": len(records),
    }


@router.post("/{connector_id}/test")
async def test_connector_connection(
    connector_id: str,
    session: AsyncSession = Depends(get_db),
    _=Depends(require_permission("connector.read")),
) -> Dict[str, Any]:
    """Test the connection for a connector.

    Args:
        connector_id: UUID string.
        session: DB session.

    Returns:
        Connection test result.
    """
    repo = ConnectorConfigRepository(session)
    connector = await repo.get(connector_id)
    if connector is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Connector '{connector_id}' not found",
        )

    if not connector_registry.is_registered(connector.type):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Connector type '{connector.type}' not registered",
        )

    inst = connector_registry.create(connector.type, config=connector.config_json)
    try:
        success = await inst.test_connection()
        return {"connector_id": connector_id, "success": success}
    except Exception as exc:
        return {"connector_id": connector_id, "success": False, "error": str(exc)}


@router.get("/{connector_id}/health")
async def get_connector_health(
    connector_id: str,
    session: AsyncSession = Depends(get_db),
    _=Depends(require_permission("connector.read")),
) -> Dict[str, Any]:
    """Get health status for a connector instance.

    Creates a temporary instance and runs a health check.

    Args:
        connector_id: UUID string.
        session: DB session.

    Returns:
        Health status with latency, last check, and details.
    """
    repo = ConnectorConfigRepository(session)
    connector = await repo.get(connector_id)
    if connector is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Connector '{connector_id}' not found",
        )

    if not connector_registry.is_registered(connector.type):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Connector type '{connector.type}' not registered",
        )

    import time

    start = time.monotonic()
    health_result: Dict[str, Any] = {}
    try:
        inst = connector_registry.create(connector.type, config=connector.config_json)
        health_result = await inst.health_check()
    except Exception as exc:
        health_result = {"status": "unhealthy", "details": {"error": str(exc)}}

    latency_ms = int((time.monotonic() - start) * 1000)
    now = datetime.now(timezone.utc).isoformat()

    return {
        "status": health_result.get("status", "unknown"),
        "connector": connector.type,
        "latency_ms": latency_ms,
        "last_check": now,
        "details": health_result.get("details", {}),
    }


@router.get("/{connector_id}/metadata")
async def get_connector_metadata(
    connector_id: str,
    session: AsyncSession = Depends(get_db),
    _=Depends(require_permission("connector.read")),
) -> Dict[str, Any]:
    """Get rich metadata for a connector (name, type, version, capabilities, config schema).

    Args:
        connector_id: UUID string.
        session: DB session.

    Returns:
        Connector metadata dict.
    """
    repo = ConnectorConfigRepository(session)
    connector = await repo.get(connector_id)
    if connector is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Connector '{connector_id}' not found",
        )

    if not connector_registry.is_registered(connector.type):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Connector type '{connector.type}' not registered",
        )

    metadata = connector_registry.get_metadata(connector.type)
    return {
        "connector_id": connector_id,
        "metadata": metadata,
        "state": lifecycle_manager.get_state(connector_id).value,
    }


@router.get("/types/metadata")
async def list_connector_types_metadata(
    _=Depends(require_permission("connector.read")),
) -> Dict[str, Any]:
    """List metadata for all registered connector types.

    Returns:
        Dict mapping type key to full metadata.
    """
    return {"types": connector_registry.get_all_metadata()}


@router.get("/types/discover")
async def discover_connectors_by_capability(
    capability: str = Query(
        ..., description="Capability to filter by (e.g., 'document_read', 'search', 'webhook')"
    ),
    _=Depends(require_permission("connector.read")),
) -> Dict[str, Any]:
    """Discover connector types that support a given capability.

    Args:
        capability: The capability string to search for.

    Returns:
        List of connector type keys that declare the capability.
    """
    matching = connector_registry.discover(capability)
    return {
        "capability": capability,
        "connectors": matching,
        "count": len(matching),
    }


@router.get("/{connector_id}/state")
async def get_connector_state(
    connector_id: str,
    session: AsyncSession = Depends(get_db),
    _=Depends(require_permission("connector.read")),
) -> Dict[str, Any]:
    """Get the lifecycle state of a connector.

    Args:
        connector_id: UUID string.
        session: DB session.

    Returns:
        Current lifecycle state.
    """
    repo = ConnectorConfigRepository(session)
    connector = await repo.get(connector_id)
    if connector is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Connector '{connector_id}' not found",
        )

    state = lifecycle_manager.get_state(connector_id)
    return {
        "connector_id": connector_id,
        "state": state.value,
        "ready": lifecycle_manager.is_ready(connector_id),
    }

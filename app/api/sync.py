"""Sync Engine API endpoints.

Provides:
    GET  /api/sync/jobs/{id}         — Get SyncJob status
    GET  /api/sync/jobs/{id}/events  — List SyncEvents for a job
    GET  /api/sync/jobs              — List SyncJobs
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_permission
from app.db.session import get_db
from app.sync_engine.job_manager import SyncJobManager

router = APIRouter(prefix="/api/sync", tags=["Sync Engine"])


@router.get("/jobs")
async def list_sync_jobs(
    connector_id: Optional[str] = Query(None),
    job_status: Optional[str] = Query(None, alias="status"),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db),
    _=Depends(require_permission("connector.read")),
) -> Dict[str, Any]:
    """List SyncJobs with optional filters.

    Args:
        connector_id: Filter by connector.
        job_status: Filter by status.
        limit: Max results.
        offset: Pagination offset.
        session: DB session.

    Returns:
        Dict with jobs list and total.
    """
    mgr = SyncJobManager(session)
    jobs = await mgr.list_jobs(
        connector_id=connector_id,
        status=job_status,
        limit=limit,
        offset=offset,
    )
    return {
        "jobs": [j.to_dict() for j in jobs],
        "total": len(jobs),
    }


@router.get("/jobs/{job_id}")
async def get_sync_job(
    job_id: str,
    session: AsyncSession = Depends(get_db),
    _=Depends(require_permission("connector.read")),
) -> Dict[str, Any]:
    """Get a SyncJob by ID.

    Args:
        job_id: SyncJob UUID.
        session: DB session.

    Returns:
        SyncJob details.
    """
    mgr = SyncJobManager(session)
    job = await mgr.get_job(job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"SyncJob '{job_id}' not found",
        )
    return job.to_dict()


@router.get("/jobs/{job_id}/events")
async def get_sync_job_events(
    job_id: str,
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db),
    _=Depends(require_permission("connector.read")),
) -> Dict[str, Any]:
    """List SyncEvents for a SyncJob.

    Args:
        job_id: SyncJob UUID.
        limit: Max results.
        offset: Pagination offset.
        session: DB session.

    Returns:
        Dict with events list and total.
    """
    mgr = SyncJobManager(session)
    job = await mgr.get_job(job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"SyncJob '{job_id}' not found",
        )

    events = await mgr.list_events(job_id, limit=limit, offset=offset)
    return {
        "sync_job_id": job_id,
        "events": [e.to_dict() for e in events],
        "total": len(events),
    }

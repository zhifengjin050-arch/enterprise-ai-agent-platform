"""Incident collector.

Collects and records incidents from various sources:
- Manual entry
- API ingestion (from Project 1's Agent)
- Automated detection
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.incident.models import IncidentRecord, IncidentStatus


async def record_incident(
    session: AsyncSession,
    title: str,
    service: str,
    severity: str,
    root_cause: Optional[str] = None,
    impact: Optional[Union[str, Dict[str, Any]]] = None,
    solution: Optional[str] = None,
    timeline: Optional[Union[str, List[Dict[str, Any]]]] = None,
    occurred_at: Optional[datetime] = None,
    detected_at: Optional[datetime] = None,
    resolved_at: Optional[datetime] = None,
    tags: Optional[List[str]] = None,
    related_sop_id: Optional[str] = None,
) -> IncidentRecord:
    """Record a new incident."""
    _ = occurred_at, detected_at, tags

    impact_json: Optional[Dict[str, Any]]
    if isinstance(impact, str):
        impact_json = {"summary": impact}
    else:
        impact_json = impact

    timeline_json: Optional[List[Dict[str, Any]]]
    if isinstance(timeline, str):
        timeline_json = [{"note": timeline}]
    else:
        timeline_json = timeline

    status = IncidentStatus.RESOLVED.value if resolved_at else IncidentStatus.NEW.value

    incident = IncidentRecord(
        title=title,
        service=service,
        severity=severity,
        status=status,
        root_cause=root_cause,
        resolution=solution,
        impact=impact_json,
        timeline=timeline_json,
        related_sop_id=related_sop_id,
    )
    session.add(incident)
    await session.flush()
    await session.refresh(incident)
    return incident


async def search_incidents(
    session: AsyncSession,
    service: Optional[str] = None,
    severity: Optional[str] = None,
    status: Optional[str] = None,
    days: int = 90,
    limit: int = 50,
    offset: int = 0,
) -> List[IncidentRecord]:
    """Search incident records with filters."""
    stmt = select(IncidentRecord)

    if service:
        stmt = stmt.where(IncidentRecord.service == service)
    if severity:
        stmt = stmt.where(IncidentRecord.severity == severity)
    if status:
        stmt = stmt.where(IncidentRecord.status == status)
    if days:
        cutoff = datetime.utcnow() - timedelta(days=days)
        stmt = stmt.where(IncidentRecord.created_at >= cutoff)

    stmt = stmt.order_by(IncidentRecord.created_at.desc()).limit(limit).offset(offset)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_incident_stats(session: AsyncSession) -> dict:
    """Get incident statistics."""
    from sqlalchemy import func as sql_func

    stmt = select(
        IncidentRecord.severity,
        sql_func.count(IncidentRecord.id),
    ).group_by(IncidentRecord.severity)
    result = await session.execute(stmt)
    severity_counts = dict(result.all())

    stmt = (
        select(IncidentRecord.service, sql_func.count(IncidentRecord.id))
        .group_by(IncidentRecord.service)
        .order_by(sql_func.count(IncidentRecord.id).desc())
        .limit(10)
    )
    result = await session.execute(stmt)
    service_counts = dict(result.all())

    return {
        "total": sum(severity_counts.values()),
        "by_severity": severity_counts,
        "by_service": service_counts,
        "avg_resolution_minutes": None,
    }

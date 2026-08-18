"""Alert rules engine — evaluates conditions and writes SystemEvent."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.observability.models import SystemEvent, SystemEventType


class AlertEngine:
    """Evaluate alert rules and write system_events."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def evaluate_all(self) -> List[SystemEvent]:
        """Evaluate all alert rules (placeholder — real rules in Grafana/Prometheus)."""
        # In-process rules are limited; real alerting is done via
        # Prometheus AlertManager with the rules defined in deploy/monitoring/alerts.yml.
        # This method exists to allow writing test coverage.
        events: List[SystemEvent] = []
        checks = [
            self._check_api_error_rate,
        ]
        for check in checks:
            try:
                result = await check()
                if result:
                    self._session.add(result)
                    events.append(result)
            except Exception:
                pass
        if events:
            await self._session.flush()
        return events

    async def _check_api_error_rate(self) -> Optional[SystemEvent]:
        """Alert if overall error rate > 5% in last 5 min (placeholder)."""
        # Placeholder — real rules run in Grafana/Prometheus
        return None

    async def write_event(
        self,
        *,
        event_type: str = SystemEventType.INFO.value,
        component: str,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        tenant_id: Optional[str] = None,
        severity: str = "info",
    ) -> SystemEvent:
        ev = SystemEvent(
            event_type=event_type,
            component=component,
            message=message,
            details_json=details or {},
            tenant_id=tenant_id,
            severity=severity,
        )
        self._session.add(ev)
        await self._session.flush()
        return ev

"""
SOP execution tracker.

Provides analytics and reporting on SOP execution history.
Tracks completion rates, average resolution times, and common failure points.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional

from app.sop.engine import ExecutionStatus, StepStatus, execution_store


class SOPStats:
    """Statistics for SOP executions."""

    def __init__(self, sop_id: str):
        self.sop_id = sop_id
        self.total_executions = 0
        self.completed_count = 0
        self.failed_count = 0
        self.aborted_count = 0
        self.avg_duration_seconds: Optional[float] = None
        self.step_failure_rates: Dict[int, float] = {}

    def to_dict(self) -> dict:
        return {
            "sop_id": self.sop_id,
            "total_executions": self.total_executions,
            "completed_count": self.completed_count,
            "failed_count": self.failed_count,
            "aborted_count": self.aborted_count,
            "success_rate": (
                round(self.completed_count / self.total_executions * 100, 1)
                if self.total_executions > 0
                else 0
            ),
            "avg_duration_seconds": self.avg_duration_seconds,
            "step_failure_rates": self.step_failure_rates,
        }


def get_execution_history(
    sop_id: Optional[str] = None,
    status: Optional[ExecutionStatus] = None,
    days: int = 30,
    limit: int = 50,
) -> List[dict]:
    """Get execution history with optional filters.

    Args:
        sop_id: Filter by SOP ID.
        status: Filter by execution status.
        days: Only include executions from the last N days.
        limit: Maximum results.

    Returns:
        List of execution summaries.
    """
    cutoff = datetime.utcnow() - timedelta(days=days)
    results = []

    for execution in execution_store._executions.values():
        if execution.started_at < cutoff:
            continue
        if sop_id and execution.sop_id != sop_id:
            continue
        if status and execution.status != status:
            continue

        results.append(execution.to_dict())
        if len(results) >= limit:
            break

    return results


def calculate_sop_stats(sop_id: str) -> SOPStats:
    """Calculate statistics for a specific SOP.

    Args:
        sop_id: SOP identifier.

    Returns:
        SOPStats instance.
    """
    stats = SOPStats(sop_id)
    executions = execution_store.get_by_sop(sop_id)

    if not executions:
        return stats

    stats.total_executions = len(executions)
    durations = []

    step_failures: Dict[int, int] = {}
    step_total: Dict[int, int] = {}

    for exec_ in executions:
        if exec_.status == ExecutionStatus.COMPLETED:
            stats.completed_count += 1
            if exec_.completed_at and exec_.started_at:
                duration = (exec_.completed_at - exec_.started_at).total_seconds()
                durations.append(duration)
        elif exec_.status == ExecutionStatus.FAILED:
            stats.failed_count += 1
        elif exec_.status == ExecutionStatus.ABORTED:
            stats.aborted_count += 1

        for step in exec_.steps:
            step_total[step.step_order] = step_total.get(step.step_order, 0) + 1
            if step.status == StepStatus.FAILED:
                step_failures[step.step_order] = step_failures.get(step.step_order, 0) + 1

    if durations:
        stats.avg_duration_seconds = sum(durations) / len(durations)

    for step_order, total in step_total.items():
        failures = step_failures.get(step_order, 0)
        stats.step_failure_rates[step_order] = round(failures / total * 100, 1) if total > 0 else 0

    return stats


def get_recent_executions(limit: int = 10) -> List[dict]:
    """Get most recent SOP executions.

    Args:
        limit: Maximum results.

    Returns:
        List of execution summaries.
    """
    return [e.to_dict() for e in execution_store.list(limit=limit)]


def get_sop_summary() -> List[dict]:
    """Get summary of all SOPs with their execution stats.

    Returns:
        List of SOP summary dicts.
    """
    from app.sop.template import list_all_sops

    summary = []
    for sop in list_all_sops():
        stats = calculate_sop_stats(sop.id)
        summary.append(
            {
                "sop_id": sop.id,
                "title": sop.title,
                "problem": sop.problem,
                "severity": sop.severity,
                "stats": stats.to_dict(),
            }
        )

    return summary

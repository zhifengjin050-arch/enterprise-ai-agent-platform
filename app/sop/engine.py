"""
SOP execution engine.

Manages the lifecycle of SOP execution: starting, tracking progress,
and completing SOP procedures step by step.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional


class StepStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


class ExecutionStatus(Enum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    ABORTED = "aborted"


@dataclass
class StepResult:
    """Result of executing a single SOP step."""

    step_order: int
    action: str
    status: StepStatus = StepStatus.PENDING
    output: Optional[str] = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


@dataclass
class SOPExecution:
    """Tracks the execution of an SOP procedure."""

    execution_id: str
    sop_id: str
    sop_title: str
    trigger: str  # manual, api, auto
    triggered_by: Optional[str] = None
    status: ExecutionStatus = ExecutionStatus.IN_PROGRESS
    current_step: int = 0
    steps: List[StepResult] = field(default_factory=list)
    started_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    context: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "execution_id": self.execution_id,
            "sop_id": self.sop_id,
            "sop_title": self.sop_title,
            "trigger": self.trigger,
            "triggered_by": self.triggered_by,
            "status": self.status.value,
            "current_step": self.current_step,
            "steps": [
                {
                    "step_order": s.step_order,
                    "action": s.action,
                    "status": s.status.value,
                    "output": s.output,
                    "error": s.error,
                }
                for s in self.steps
            ],
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error": self.error,
        }


class ExecutionStore:
    """In-memory store for SOP executions.

    TODO: Replace with database-backed storage.
    """

    def __init__(self):
        self._executions: dict[str, SOPExecution] = {}

    def add(self, execution: SOPExecution) -> None:
        self._executions[execution.execution_id] = execution

    def get(self, execution_id: str) -> Optional[SOPExecution]:
        return self._executions.get(execution_id)

    def update(self, execution: SOPExecution) -> None:
        self._executions[execution.execution_id] = execution

    def list(self, limit: int = 20, offset: int = 0) -> List[SOPExecution]:
        all_execs = list(self._executions.values())
        all_execs.sort(key=lambda e: e.started_at, reverse=True)
        return all_execs[offset : offset + limit]

    def get_by_sop(self, sop_id: str) -> List[SOPExecution]:
        return [e for e in self._executions.values() if e.sop_id == sop_id]


# Global execution store
execution_store = ExecutionStore()


def create_execution(
    sop_id: str,
    sop_title: str,
    steps: List[dict],
    trigger: str = "manual",
    triggered_by: Optional[str] = None,
) -> SOPExecution:
    """Create a new SOP execution.

    Args:
        sop_id: SOP identifier.
        sop_title: SOP title.
        steps: List of step definitions (from SOP template).
        trigger: How the execution was triggered.
        triggered_by: Who triggered the execution.

    Returns:
        New SOPExecution instance.
    """
    import uuid

    execution = SOPExecution(
        execution_id=str(uuid.uuid4()),
        sop_id=sop_id,
        sop_title=sop_title,
        trigger=trigger,
        triggered_by=triggered_by,
        steps=[
            StepResult(
                step_order=s.get("order", i + 1),
                action=s.get("action", ""),
            )
            for i, s in enumerate(steps)
        ],
    )
    execution_store.add(execution)
    return execution


def update_step_status(
    execution_id: str,
    step_order: int,
    status: StepStatus,
    output: Optional[str] = None,
    error: Optional[str] = None,
) -> Optional[SOPExecution]:
    """Update the status of a step in an execution.

    Args:
        execution_id: Execution identifier.
        step_order: Step order number.
        status: New step status.
        output: Step execution output.
        error: Step error message.

    Returns:
        Updated execution or None if not found.
    """
    execution = execution_store.get(execution_id)
    if not execution:
        return None

    for step in execution.steps:
        if step.step_order == step_order:
            step.status = status
            step.output = output
            step.error = error
            if status in (StepStatus.RUNNING,):
                step.started_at = datetime.utcnow()
            if status in (StepStatus.SUCCESS, StepStatus.FAILED, StepStatus.SKIPPED):
                step.completed_at = datetime.utcnow()
            break

    execution.current_step = step_order

    # Check if all steps completed
    all_done = all(
        s.status in (StepStatus.SUCCESS, StepStatus.FAILED, StepStatus.SKIPPED)
        for s in execution.steps
    )
    if all_done:
        execution.status = ExecutionStatus.COMPLETED
        execution.completed_at = datetime.utcnow()

    execution_store.update(execution)
    return execution


def abort_execution(execution_id: str) -> Optional[SOPExecution]:
    """Abort an ongoing SOP execution.

    Args:
        execution_id: Execution identifier.

    Returns:
        Updated execution or None if not found.
    """
    execution = execution_store.get(execution_id)
    if not execution:
        return None

    execution.status = ExecutionStatus.ABORTED
    execution.completed_at = datetime.utcnow()
    execution_store.update(execution)
    return execution

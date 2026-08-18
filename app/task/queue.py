"""Background task queue for async workflow execution.

Provides in-process queue (backed by database) for document
import tasks. Designed for Redis/Celery upgrade path.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from app.task.models import TaskRecord, TaskStatus


class TaskQueue:
    """In-process async task queue.

    Maintains a database-backed task record and supports
    registration of worker handlers per task type.

    Args:
        handler: Optional callable to process tasks.
                  Signature: async def handler(task: TaskRecord) -> Dict[str, Any]
    """

    def __init__(self, handler: Optional[Callable] = None):
        self._handler = handler
        self._processing: set = set()

    async def enqueue(
        self,
        session,
        *,
        task_type: str = "document_import",
        payload: Optional[Dict[str, Any]] = None,
    ) -> TaskRecord:
        """Enqueue a new task.

        Args:
            session: AsyncSession for persistence.
            task_type: Type of task.
            payload: Task input data.

        Returns:
            TaskRecord with status='queued'.
        """
        record = TaskRecord(
            task_type=task_type,
            status=TaskStatus.QUEUED.value,
            payload=payload or {},
        )
        session.add(record)
        await session.flush()
        await session.refresh(record)
        return record

    async def get_task(
        self,
        session,
        task_id: str,
    ) -> Optional[TaskRecord]:
        """Get a task record by ID.

        Args:
            session: AsyncSession.
            task_id: Task UUID string.

        Returns:
            TaskRecord or None.
        """
        from sqlalchemy import select

        stmt = select(TaskRecord).where(TaskRecord.id == task_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def update_status(
        self,
        session,
        task_id: str,
        *,
        status: str,
        result: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> Optional[TaskRecord]:
        """Update a task's status and result.

        Args:
            session: AsyncSession.
            task_id: Task UUID.
            status: New status.
            result: Optional result data.
            error: Optional error message.

        Returns:
            Updated TaskRecord or None.
        """
        task = await self.get_task(session, task_id)
        if task is None:
            return None
        task.status = status
        if result is not None:
            task.result = result
        if error is not None:
            task.error = error
        await session.flush()
        return task

    async def list_tasks(
        self,
        session,
        *,
        status: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> List[TaskRecord]:
        """List tasks with optional status filter.

        Args:
            session: AsyncSession.
            status: Optional status filter.
            limit: Max results.
            offset: Pagination offset.

        Returns:
            List of TaskRecord.
        """
        from sqlalchemy import select

        stmt = select(TaskRecord).order_by(TaskRecord.created_at.desc())
        if status is not None:
            stmt = stmt.where(TaskRecord.status == status)
        stmt = stmt.limit(limit).offset(offset)
        result = await session.execute(stmt)
        return list(result.scalars().all())

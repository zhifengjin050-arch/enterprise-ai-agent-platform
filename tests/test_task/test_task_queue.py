"""Tests for task queue operations."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.task.models import TaskRecord
from app.task.queue import TaskQueue


@pytest.fixture
def mock_session() -> AsyncMock:
    """Create a mock AsyncSession."""
    session = AsyncMock()
    session.execute = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    return session


class TestTaskQueue:
    """Test TaskQueue operations."""

    async def test_enqueue(self, mock_session: AsyncMock) -> None:
        """Test enqueuing a task."""
        queue = TaskQueue()
        task = await queue.enqueue(
            mock_session,
            task_type="document_import",
            payload={"title": "Test"},
        )
        mock_session.add.assert_called_once()
        mock_session.flush.assert_awaited_once()
        assert task.status == "queued"
        assert task.task_type == "document_import"

    async def test_get_task_found(self, mock_session: AsyncMock) -> None:
        """Test getting a task by ID — found."""
        mock_task = MagicMock(spec=TaskRecord)
        mock_task.id = "task-123"
        mock_task.status = "queued"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_task
        mock_session.execute.return_value = mock_result

        queue = TaskQueue()
        task = await queue.get_task(mock_session, "task-123")
        assert task is not None
        assert task.id == "task-123"

    async def test_get_task_not_found(self, mock_session: AsyncMock) -> None:
        """Test getting a task by ID — not found."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        queue = TaskQueue()
        task = await queue.get_task(mock_session, "nonexistent")
        assert task is None

    async def test_update_status(self, mock_session: AsyncMock) -> None:
        """Test updating task status."""
        mock_task = MagicMock(spec=TaskRecord)
        mock_task.id = "task-456"
        mock_task.status = "queued"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_task
        mock_session.execute.return_value = mock_result

        queue = TaskQueue()
        updated = await queue.update_status(
            mock_session,
            "task-456",
            status="running",
        )
        assert updated is not None
        assert updated.status == "running"

    async def test_update_status_with_result(self, mock_session: AsyncMock) -> None:
        """Test updating task with result."""
        mock_task = MagicMock(spec=TaskRecord)
        mock_task.id = "task-789"
        mock_task.status = "running"
        mock_task.result = None

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_task
        mock_session.execute.return_value = mock_result

        queue = TaskQueue()
        updated = await queue.update_status(
            mock_session,
            "task-789",
            status="success",
            result={"document_id": "doc-123"},
        )
        assert updated is not None
        assert updated.status == "success"

    async def test_update_status_failed(self, mock_session: AsyncMock) -> None:
        """Test updating task as failed with error."""
        mock_task = MagicMock(spec=TaskRecord)
        mock_task.id = "task-fail"
        mock_task.status = "running"
        mock_task.error = None

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_task
        mock_session.execute.return_value = mock_result

        queue = TaskQueue()
        updated = await queue.update_status(
            mock_session,
            "task-fail",
            status="failed",
            error="Something went wrong",
        )
        assert updated is not None
        assert updated.status == "failed"

    async def test_list_tasks(self, mock_session: AsyncMock) -> None:
        """Test listing tasks."""
        mock_task1 = MagicMock(spec=TaskRecord)
        mock_task1.id = "task-1"
        mock_task2 = MagicMock(spec=TaskRecord)
        mock_task2.id = "task-2"

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_task1, mock_task2]
        mock_session.execute.return_value = mock_result

        queue = TaskQueue()
        tasks = await queue.list_tasks(mock_session)
        assert len(tasks) == 2
"""Tests for task queue models."""

from __future__ import annotations

from app.task.models import TaskRecord, TaskStatus


class TestTaskStatus:
    """Test TaskStatus enum."""

    def test_enum_values(self) -> None:
        """Test all expected status values."""
        assert TaskStatus.QUEUED.value == "queued"
        assert TaskStatus.RUNNING.value == "running"
        assert TaskStatus.SUCCESS.value == "success"
        assert TaskStatus.FAILED.value == "failed"


class TestTaskRecord:
    """Test TaskRecord model."""

    def test_create_task(self) -> None:
        """Test creating a task record with explicit fields."""
        task = TaskRecord(
            task_type="document_import",
            status="queued",
            payload={"title": "Test Doc", "content": "Hello"},
        )
        assert task.task_type == "document_import"
        assert task.status == "queued"
        assert task.payload == {"title": "Test Doc", "content": "Hello"}

    def test_task_fields(self) -> None:
        """Test setting various task fields."""
        task = TaskRecord(
            task_type="custom_type",
            status="running",
        )
        assert task.task_type == "custom_type"
        assert task.status == "running"
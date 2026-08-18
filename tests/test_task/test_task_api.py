"""Tests for task API endpoints."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app


@pytest.fixture
def client() -> AsyncClient:
    """Create test AsyncClient with ASGITransport."""
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


class TestTaskAPI:
    """Test /api/tasks endpoints."""

    @patch("app.api.task.TaskQueue")
    async def test_create_import_task(
        self, mock_queue: MagicMock, client: AsyncClient
    ) -> None:
        """Test creating a document import task."""
        mock_queue_instance = AsyncMock()
        mock_task = MagicMock()
        mock_task.id = "task-uuid-123"
        mock_task.status = "queued"
        mock_queue_instance.enqueue = AsyncMock(return_value=mock_task)
        mock_queue.return_value = mock_queue_instance

        response = await client.post(
            "/api/tasks/document/import",
            json={
                "title": "Test Document",
                "content": "This is test content.",
                "metadata": {"source": "test"},
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["task_id"] == "task-uuid-123"
        assert data["status"] == "queued"

    @patch("app.api.task.TaskQueue")
    async def test_get_task_status(
        self, mock_queue: MagicMock, client: AsyncClient
    ) -> None:
        """Test getting task status."""
        mock_queue_instance = AsyncMock()
        mock_task = MagicMock()
        mock_task.id = "task-uuid-456"
        mock_task.status = "success"
        mock_task.result = {"document_id": "doc-123", "status": "completed"}
        mock_task.error = None
        mock_task.created_at = MagicMock()
        mock_task.created_at.isoformat.return_value = "2026-01-01T00:00:00+00:00"

        mock_queue_instance.get_task = AsyncMock(return_value=mock_task)
        mock_queue.return_value = mock_queue_instance

        response = await client.get("/api/tasks/task-uuid-456")
        assert response.status_code == 200
        data = response.json()
        assert data["task_id"] == "task-uuid-456"
        assert data["status"] == "success"
        assert data["result"]["document_id"] == "doc-123"

    @patch("app.api.task.TaskQueue")
    async def test_get_task_not_found(
        self, mock_queue: MagicMock, client: AsyncClient
    ) -> None:
        """Test getting non-existent task returns 404."""
        mock_queue_instance = AsyncMock()
        mock_queue_instance.get_task = AsyncMock(return_value=None)
        mock_queue.return_value = mock_queue_instance

        response = await client.get("/api/tasks/nonexistent")
        assert response.status_code == 404

    @patch("app.api.task.TaskQueue")
    async def test_list_tasks(
        self, mock_queue: MagicMock, client: AsyncClient
    ) -> None:
        """Test listing tasks."""
        mock_t1 = MagicMock()
        mock_t1.id = "task-1"
        mock_t1.task_type = "document_import"
        mock_t1.status = "queued"
        mock_t1.created_at = MagicMock()
        mock_t1.created_at.isoformat.return_value = "2026-01-01T00:00:00+00:00"

        mock_t2 = MagicMock()
        mock_t2.id = "task-2"
        mock_t2.task_type = "document_import"
        mock_t2.status = "success"
        mock_t2.created_at = MagicMock()
        mock_t2.created_at.isoformat.return_value = "2026-01-02T00:00:00+00:00"

        mock_queue_instance = AsyncMock()
        mock_queue_instance.list_tasks = AsyncMock(return_value=[mock_t1, mock_t2])
        mock_queue.return_value = mock_queue_instance

        response = await client.get("/api/tasks/")
        assert response.status_code == 200
        data = response.json()
        assert len(data["tasks"]) == 2
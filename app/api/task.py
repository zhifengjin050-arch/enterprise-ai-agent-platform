"""Task API endpoints for async document import."""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.task.queue import TaskQueue

router = APIRouter(prefix="/api/tasks", tags=["Tasks"])


class DocumentImportRequest(BaseModel):
    """Document import task request."""

    title: str = "Imported Document"
    content: str = ""
    file_path: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class TaskStatusResponse(BaseModel):
    """Task status response."""

    task_id: str
    status: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


@router.post("/document/import")
async def create_import_task(
    request: DocumentImportRequest,
    session: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Create a document import task.

    Args:
        request: Document content and metadata.
        session: DB session.

    Returns:
        Task ID and status.
    """
    queue = TaskQueue()
    task = await queue.enqueue(
        session,
        task_type="document_import",
        payload={
            "title": request.title,
            "content": request.content,
            "file_path": request.file_path,
            "metadata": request.metadata or {},
        },
    )
    await session.commit()

    return {
        "task_id": task.id,
        "status": task.status,
    }


@router.get("/{task_id}")
async def get_task_status(
    task_id: str,
    session: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Get task status by ID.

    Args:
        task_id: Task UUID string.
        session: DB session.

    Returns:
        Task status and result if completed.
    """
    queue = TaskQueue()
    task = await queue.get_task(session, task_id)
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task '{task_id}' not found",
        )
    return {
        "task_id": task.id,
        "status": task.status,
        "result": task.result,
        "error": task.error,
        "created_at": task.created_at.isoformat() if task.created_at else None,
    }


@router.get("/")
async def list_tasks(
    status_filter: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
    session: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """List tasks with optional status filter.

    Args:
        status_filter: Optional status (queued/running/success/failed).
        limit: Max results.
        offset: Pagination offset.
        session: DB session.

    Returns:
        Dict with tasks list.
    """
    queue = TaskQueue()
    tasks = await queue.list_tasks(session, status=status_filter, limit=limit, offset=offset)
    return {
        "tasks": [
            {
                "task_id": t.id,
                "task_type": t.task_type,
                "status": t.status,
                "created_at": t.created_at.isoformat() if t.created_at else None,
            }
            for t in tasks
        ],
        "total": len(tasks),
    }

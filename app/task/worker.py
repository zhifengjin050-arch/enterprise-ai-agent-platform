"""Background task worker.

Polls the task queue and processes pending document import
tasks by running the knowledge workflow pipeline.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional

from app.db.session import get_session_factory
from app.task.models import TaskStatus
from app.task.queue import TaskQueue
from app.workflow.knowledge_pipeline import knowledge_pipeline
from app.workflow.state import KnowledgeState

logger = logging.getLogger(__name__)


class TaskWorker:
    """Background worker that processes queued tasks.

    Polls the database for queued tasks and executes them.
    Intended to run in a separate process/thread.

    Args:
        task_queue: Optional TaskQueue override.
    """

    def __init__(self, task_queue: Optional[TaskQueue] = None):
        self._queue = task_queue or TaskQueue()
        self._running = False

    async def start(self, poll_interval: float = 2.0) -> None:
        """Start the worker polling loop.

        Args:
            poll_interval: Seconds between polls.
        """
        self._running = True
        logger.info("TaskWorker started")
        while self._running:
            try:
                await self._process_next()
            except Exception as e:
                logger.error(f"TaskWorker error: {e}")
            await asyncio.sleep(poll_interval)

    def stop(self) -> None:
        """Stop the worker."""
        self._running = False
        logger.info("TaskWorker stopped")

    async def _process_next(self) -> None:
        """Process the next queued task."""
        factory = get_session_factory()
        async with factory() as session:
            queue = self._queue or TaskQueue()
            tasks = await queue.list_tasks(session, status=TaskStatus.QUEUED.value, limit=1)
            if not tasks:
                return

            task = tasks[0]
            await queue.update_status(session, task.id, status=TaskStatus.RUNNING.value)
            await session.commit()

        # Execute workflow outside the session (workflow creates its own sessions)
        try:
            payload = task.payload or {}
            result = await self._execute_workflow(payload)

            async with factory() as session:
                await queue.update_status(
                    session, task.id,
                    status=TaskStatus.SUCCESS.value,
                    result=result,
                )
                await session.commit()

        except Exception as e:
            async with factory() as session:
                await queue.update_status(
                    session, task.id,
                    status=TaskStatus.FAILED.value,
                    error=str(e),
                )
                await session.commit()

    async def _execute_workflow(
        self, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute the knowledge pipeline workflow.

        Args:
            payload: Task payload with document data.

        Returns:
            Workflow result dict.
        """
        content = payload.get("content", "")
        title = payload.get("title", "Imported Document")
        file_path = payload.get("file_path")

        state: KnowledgeState = {
            "raw_content": content,
            "title": title,
            "file_path": file_path,
            "document_id": payload.get("document_id", ""),
            "status": "processing",
            "tags": [],
            "quality_score": 0.0,
            "quality_issues": [],
            "stored": False,
            "indexed": False,
            "need_review": False,
            "metadata": payload.get("metadata", {}),
            "entities": [],
            "relations": [],
        }

        pipeline = knowledge_pipeline
        result = pipeline(state)
        if asyncio.iscoroutine(result):
            result = await result

        return {
            "document_id": result.get("document_id"),
            "status": result.get("status", "completed"),
            "stored": result.get("stored", False),
            "indexed": result.get("indexed", False),
        }

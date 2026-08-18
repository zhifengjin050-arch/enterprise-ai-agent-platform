"""Workflow orchestrator - unified entry point for pipeline execution.

Provides sync and async execution interfaces for the knowledge pipeline,
with state persistence, resume capability, and human-in-the-loop support.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.db.session import get_session_factory
from app.workflow.knowledge_pipeline import knowledge_pipeline
from app.workflow.state import KnowledgeState


class WorkflowOrchestrator:
    """Unified workflow orchestrator for knowledge processing.

    Manages the full lifecycle of a document through the LangGraph pipeline,
    including persistence, error recovery, and human review approval/rejection.
    """

    async def process_document(
        self,
        document_id: str,
        raw_content: str,
        title: Optional[str] = None,
        file_path: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Submit a document into the knowledge workflow pipeline.

        Creates a WorkflowRun record, executes the pipeline, and
        persists the final state.

        Args:
            document_id: Unique identifier for the document.
            raw_content: Raw text content to process.
            title: Optional document title.
            file_path: Optional source file path.
            metadata: Optional metadata dict.

        Returns:
            Final workflow state as a plain dict.
        """
        workflow_run_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        initial: KnowledgeState = {
            "document_id": document_id,
            "file_path": file_path,
            "workflow_run_id": workflow_run_id,
            "raw_content": raw_content,
            "markdown_content": None,
            "title": title or "Untitled",
            "doc_type": None,
            "tags": [],
            "quality_score": 0.0,
            "quality_issues": [],
            "embedding_id": None,
            "stored": False,
            "indexed": False,
            "need_review": False,
            "review_decision": None,
            "review_comment": None,
            "status": "processing",
            "current_node": None,
            "error": None,
            "metadata": metadata or {},
        }

        # Persist initial workflow run
        await self._save_workflow_run(
            workflow_run_id=workflow_run_id,
            document_id=document_id,
            state=initial,
            status="processing",
            current_node=None,
        )

        try:
            pipeline = knowledge_pipeline

            if hasattr(pipeline, "ainvoke"):
                result: KnowledgeState = await pipeline.ainvoke(initial)
            else:
                # Sequential fallback (runs in event loop)
                result = pipeline(initial)

            final_status = "completed"
            if result.get("error"):
                final_status = "failed"
            elif result.get("need_review") and result.get("review_decision") != "approved":
                final_status = "review"

            await self._save_workflow_run(
                workflow_run_id=workflow_run_id,
                document_id=document_id,
                state=result,
                status=final_status,
                current_node=result.get("current_node"),
                error=result.get("error"),
            )

            return dict(result)

        except Exception as exc:
            error_msg = f"Pipeline execution failed: {exc}"
            await self._save_workflow_run(
                workflow_run_id=workflow_run_id,
                document_id=document_id,
                state=initial,
                status="failed",
                current_node=None,
                error=error_msg,
            )
            return {
                "document_id": document_id,
                "status": "failed",
                "error": error_msg,
            }

    async def get_workflow_run(self, workflow_run_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve the state of a workflow run by its id.

        Args:
            workflow_run_id: The workflow run UUID.

        Returns:
            Dict with workflow run data, or None if not found.
        """
        from app.workflow.models import WorkflowRun

        factory = get_session_factory()
        async with factory() as session:
            from sqlalchemy import select

            result = await session.execute(
                select(WorkflowRun).where(WorkflowRun.id == workflow_run_id)
            )
            run = result.scalar_one_or_none()
            if run is None:
                return None
            return {
                "id": run.id,
                "workflow_type": run.workflow_type,
                "document_id": run.document_id,
                "status": run.status,
                "current_node": run.current_node,
                "state": run.state_json,
                "error": run.error,
                "created_at": run.created_at.isoformat() if run.created_at else None,
                "updated_at": run.updated_at.isoformat() if run.updated_at else None,
            }

    async def approve_review(
        self,
        workflow_run_id: str,
        comment: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Approve a document that is waiting in human review.

        Resumes the workflow from the review point.

        Args:
            workflow_run_id: The workflow run UUID.
            comment: Optional reviewer comment.

        Returns:
            Updated workflow state.
        """
        from app.workflow.models import WorkflowRun

        factory = get_session_factory()
        async with factory() as session:
            from sqlalchemy import select

            result = await session.execute(
                select(WorkflowRun).where(WorkflowRun.id == workflow_run_id)
            )
            run = result.scalar_one_or_none()
            if run is None:
                return {"error": f"WorkflowRun {workflow_run_id} not found"}

            if run.status != "review":
                return {"error": f"WorkflowRun is not in review status (current: {run.status})"}

            state: KnowledgeState = dict(run.state_json or {})
            state["review_decision"] = "approved"
            state["review_comment"] = comment
            state["status"] = "processing"

        # Resume the pipeline from the review checkpoint
        try:
            pipeline = knowledge_pipeline

            if hasattr(pipeline, "ainvoke"):
                result_state: KnowledgeState = await pipeline.ainvoke(state)
            else:
                result_state = pipeline(state)

            final_status = "completed"
            if result_state.get("error"):
                final_status = "failed"

            await self._save_workflow_run(
                workflow_run_id=workflow_run_id,
                document_id=result_state.get("document_id", ""),
                state=result_state,
                status=final_status,
                current_node=result_state.get("current_node"),
                error=result_state.get("error"),
            )

            return dict(result_state)

        except Exception as exc:
            error_msg = f"Resume after approval failed: {exc}"
            await self._save_workflow_run(
                workflow_run_id=workflow_run_id,
                document_id=state.get("document_id", ""),
                state=state,
                status="failed",
                current_node=None,
                error=error_msg,
            )
            return {"error": error_msg}

    async def reject_review(
        self,
        workflow_run_id: str,
        comment: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Reject a document in human review.

        Marks the workflow as failed with the rejection reason.

        Args:
            workflow_run_id: The workflow run UUID.
            comment: Optional rejection reason.

        Returns:
            Final workflow state.
        """
        from app.workflow.models import WorkflowRun

        factory = get_session_factory()
        async with factory() as session:
            from sqlalchemy import select

            result = await session.execute(
                select(WorkflowRun).where(WorkflowRun.id == workflow_run_id)
            )
            run = result.scalar_one_or_none()
            if run is None:
                return {"error": f"WorkflowRun {workflow_run_id} not found"}

            if run.status != "review":
                return {"error": f"WorkflowRun is not in review status (current: {run.status})"}

            state: KnowledgeState = dict(run.state_json or {})
            state["review_decision"] = "rejected"
            state["review_comment"] = comment
            state["status"] = "completed"
            state["error"] = f"Rejected by human review: {comment}" if comment else "Rejected by human review"

            await self._save_workflow_run(
                workflow_run_id=workflow_run_id,
                document_id=run.document_id or "",
                state=state,
                status="completed",
                current_node="review",
                error=state.get("error"),
            )

        return dict(state)

    @staticmethod
    async def _save_workflow_run(
        workflow_run_id: str,
        document_id: str,
        state: KnowledgeState,
        status: str,
        current_node: Optional[str] = None,
        error: Optional[str] = None,
    ) -> None:
        """Create or update a WorkflowRun record in the database."""
        from app.workflow.models import WorkflowRun

        factory = get_session_factory()
        async with factory() as session:
            from sqlalchemy import select

            result = await session.execute(
                select(WorkflowRun).where(WorkflowRun.id == workflow_run_id)
            )
            run = result.scalar_one_or_none()

            state_copy: Dict[str, Any] = {}
            for k, v in state.items():
                try:
                    json.dumps(v)
                    state_copy[k] = v
                except (TypeError, OverflowError):
                    state_copy[k] = str(v)

            if run is None:
                run = WorkflowRun(
                    id=workflow_run_id,
                    workflow_type="knowledge",
                    document_id=document_id or None,
                    status=status,
                    current_node=current_node,
                    state_json=state_copy,
                    error=error,
                )
                session.add(run)
            else:
                run.status = status
                run.current_node = current_node
                run.state_json = state_copy
                run.error = error
                run.updated_at = datetime.now(timezone.utc)

            await session.commit()


# Module-level singleton
orchestrator: WorkflowOrchestrator = WorkflowOrchestrator()

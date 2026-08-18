"""Workflow API routes.

Provides endpoints for submitting documents into the knowledge workflow,
checking execution status, and handling human-in-the-loop review approvals.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException

from app.workflow.orchestrator import orchestrator

router = APIRouter(prefix="/api/workflow", tags=["workflow"])


@router.post("/document/import")
async def import_document(
    document_id: str,
    raw_content: str,
    title: Optional[str] = None,
    file_path: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Submit a document into the knowledge processing workflow.

    The document will go through parse → classify → tag → quality →
    (embed → store → index) or (review → ...) depending on quality score.
    """
    try:
        result = await orchestrator.process_document(
            document_id=document_id,
            raw_content=raw_content,
            title=title,
            file_path=file_path,
            metadata=metadata,
        )
        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/{workflow_id}")
async def get_workflow_status(workflow_id: str) -> Dict[str, Any]:
    """Get the current status of a workflow execution.

    Args:
        workflow_id: The workflow run UUID.

    Returns:
        WorkflowRun data including status, current_node, state snapshot.
    """
    try:
        result = await orchestrator.get_workflow_run(workflow_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Workflow run not found")
        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/{workflow_id}/approve")
async def approve_review(
    workflow_id: str,
    comment: Optional[str] = None,
) -> Dict[str, Any]:
    """Approve a document that is waiting in human review.

    Resumes the pipeline: review → embed → store → index.

    Args:
        workflow_id: The workflow run UUID.
        comment: Optional reviewer comment.
    """
    try:
        result = await orchestrator.approve_review(
            workflow_run_id=workflow_id,
            comment=comment,
        )
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/{workflow_id}/reject")
async def reject_review(
    workflow_id: str,
    comment: Optional[str] = None,
) -> Dict[str, Any]:
    """Reject a document in human review.

    Marks the workflow as completed with a rejection reason.

    Args:
        workflow_id: The workflow run UUID.
        comment: Optional rejection reason.
    """
    try:
        result = await orchestrator.reject_review(
            workflow_run_id=workflow_id,
            comment=comment,
        )
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

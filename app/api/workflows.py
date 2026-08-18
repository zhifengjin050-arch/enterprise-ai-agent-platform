"""Workflow Engine API — Phase 9 Enterprise AI Workflow Automation Engine.

Endpoints:
    POST   /api/workflows              — Create a workflow definition
    GET    /api/workflows              — List workflow definitions
    GET    /api/workflows/{id}         — Get workflow definition
    POST   /api/workflows/{id}/execute — Execute (start) a workflow
    GET    /api/workflows/{id}/runs    — List runs for a workflow
    POST   /api/workflows/{id}/cancel  — Cancel a specific run

Run-level:
    GET    /api/workflows/runs/{run_id}      — Get run details
    POST   /api/workflows/runs/{run_id}/pause   — Pause a running run
    POST   /api/workflows/runs/{run_id}/resume  — Resume a paused run
    POST   /api/workflows/runs/{run_id}/cancel  — Cancel a run

Approval:
    POST   /api/workflows/approvals/{approval_id}/approve — Approve
    POST   /api/workflows/approvals/{approval_id}/reject  — Reject
    GET    /api/workflows/approvals/{approval_id}        — Get approval status

Events:
    GET    /api/workflows/runs/{run_id}/events — Get run audit events

Webhook:
    POST   /api/workflows/webhook/{workflow_id} — Trigger via webhook
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException

from app.auth.dependencies import get_optional_current_user, require_permission
from app.workflow_engine.approval import approval_service
from app.workflow_engine.engine import workflow_engine
from app.workflow_engine.parser import WorkflowValidationError

router = APIRouter(prefix="/api/workflows", tags=["workflows", "phase9"])


# ──────────────────────────────────────────────
# Workflow Definition CRUD
# ──────────────────────────────────────────────


@router.post("")
async def create_workflow(
    body: Dict[str, Any],
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_current_user),
    _=Depends(require_permission("admin.workflow")),
) -> Dict[str, Any]:
    """Create a new workflow definition from JSON DSL."""
    try:
        tenant_id = current_user.get("tenant_id") if current_user else None
        created_by = current_user.get("id") if current_user else None
        result = await workflow_engine.create_workflow(
            definition=body,
            tenant_id=tenant_id,
            created_by=created_by,
        )
        return result
    except WorkflowValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("")
async def list_workflows(
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_current_user),
    _=Depends(require_permission("admin.workflow")),
) -> List[Dict[str, Any]]:
    """List workflow definitions with optional status filter."""
    try:
        tenant_id = current_user.get("tenant_id") if current_user else None
        from app.workflow_engine.models import WorkflowStatus
        status_enum = WorkflowStatus(status.upper()) if status else None
        return await workflow_engine.get_workflows(
            tenant_id=tenant_id,
            status=status_enum,
            limit=limit,
            offset=offset,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/{workflow_id}")
async def get_workflow(
    workflow_id: str,
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_current_user),
    _=Depends(require_permission("admin.workflow")),
) -> Dict[str, Any]:
    """Get a workflow definition by ID."""
    try:
        tenant_id = current_user.get("tenant_id") if current_user else None
        result = await workflow_engine.get_workflow(workflow_id, tenant_id=tenant_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Workflow not found")
        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ──────────────────────────────────────────────
# Execution
# ──────────────────────────────────────────────


@router.post("/{workflow_id}/execute")
async def execute_workflow(
    workflow_id: str,
    body: Optional[Dict[str, Any]] = None,
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_current_user),
    _=Depends(require_permission("admin.workflow")),
) -> Dict[str, Any]:
    """Execute (start) a workflow by its definition ID.

    Optional body can include trigger_type and trigger_payload.
    """
    body = body or {}
    try:
        tenant_id = current_user.get("tenant_id") if current_user else None
        triggered_by = current_user.get("id") if current_user else None
        result = await workflow_engine.execute_workflow(
            workflow_id=workflow_id,
            trigger_type=body.get("trigger_type", "api"),
            trigger_payload=body.get("payload", {}),
            tenant_id=tenant_id,
            triggered_by=triggered_by,
        )
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/{workflow_id}/runs")
async def list_runs(
    workflow_id: str,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_current_user),
    _=Depends(require_permission("admin.workflow")),
) -> List[Dict[str, Any]]:
    """List execution runs for a workflow."""
    try:
        tenant_id = current_user.get("tenant_id") if current_user else None
        from app.workflow_engine.models import WorkflowStatus
        status_enum = WorkflowStatus(status.upper()) if status else None
        return await workflow_engine.get_runs(
            workflow_id=workflow_id,
            tenant_id=tenant_id,
            status=status_enum,
            limit=limit,
            offset=offset,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ──────────────────────────────────────────────
# Run-level operations
# ──────────────────────────────────────────────


@router.get("/runs/{run_id}")
async def get_run(
    run_id: str,
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_current_user),
    _=Depends(require_permission("admin.workflow")),
) -> Dict[str, Any]:
    """Get details of a specific workflow run."""
    try:
        tenant_id = current_user.get("tenant_id") if current_user else None
        result = await workflow_engine.get_run(run_id, tenant_id=tenant_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Run not found")
        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/runs/{run_id}/pause")
async def pause_run(
    run_id: str,
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_current_user),
    _=Depends(require_permission("admin.workflow")),
) -> Dict[str, Any]:
    """Pause a running workflow execution."""
    try:
        tenant_id = current_user.get("tenant_id") if current_user else None
        result = await workflow_engine.pause_workflow(run_id, tenant_id=tenant_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Run not found")
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/runs/{run_id}/resume")
async def resume_run(
    run_id: str,
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_current_user),
    _=Depends(require_permission("admin.workflow")),
) -> Dict[str, Any]:
    """Resume a paused workflow execution."""
    try:
        tenant_id = current_user.get("tenant_id") if current_user else None
        result = await workflow_engine.resume_workflow(run_id, tenant_id=tenant_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Run not found")
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/{workflow_id}/cancel")
async def cancel_workflow(
    workflow_id: str,
    body: Optional[Dict[str, Any]] = None,
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_current_user),
    _=Depends(require_permission("admin.workflow")),
) -> Dict[str, Any]:
    """Cancel the latest running run for a workflow (by workflow ID)."""
    body = body or {}
    try:
        tenant_id = current_user.get("tenant_id") if current_user else None
        # Find the latest RUNNING run for this workflow
        runs = await workflow_engine.get_runs(
            workflow_id=workflow_id,
            tenant_id=tenant_id,
            status=None,
            limit=10,
            offset=0,
        )
        # Find a cancellable run
        for r in runs:
            if r.get("status") in ("RUNNING", "PAUSED", "WAITING"):
                result = await workflow_engine.cancel_workflow(
                    r["id"], tenant_id=tenant_id,
                )
                return result or {"status": "cancelled", "run_id": r["id"]}

        raise HTTPException(
            status_code=400,
            detail="No running/paused/waiting run found to cancel",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/runs/{run_id}/cancel")
async def cancel_run(
    run_id: str,
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_current_user),
    _=Depends(require_permission("admin.workflow")),
) -> Dict[str, Any]:
    """Cancel a specific workflow run."""
    try:
        tenant_id = current_user.get("tenant_id") if current_user else None
        result = await workflow_engine.cancel_workflow(run_id, tenant_id=tenant_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Run not found")
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ──────────────────────────────────────────────
# Events
# ──────────────────────────────────────────────


@router.get("/runs/{run_id}/events")
async def get_run_events(
    run_id: str,
    limit: int = 100,
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_current_user),
    _=Depends(require_permission("admin.workflow")),
) -> List[Dict[str, Any]]:
    """Get audit events for a specific workflow run."""
    try:
        tenant_id = current_user.get("tenant_id") if current_user else None
        return await workflow_engine.get_run_events(
            run_id=run_id, tenant_id=tenant_id, limit=limit,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ──────────────────────────────────────────────
# Approval
# ──────────────────────────────────────────────


@router.get("/approvals/{approval_id}")
async def get_approval(
    approval_id: str,
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_current_user),
) -> Dict[str, Any]:
    """Get approval status."""
    try:
        result = await approval_service.get_approval(approval_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Approval not found")
        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/approvals/{approval_id}/approve")
async def approve_approval(
    approval_id: str,
    body: Optional[Dict[str, Any]] = None,
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_current_user),
    _=Depends(require_permission("admin.workflow")),
) -> Dict[str, Any]:
    """Approve a pending approval request."""
    body = body or {}
    try:
        user_id = current_user.get("id", "unknown") if current_user else "system"
        result = await approval_service.approve(
            approval_id=approval_id,
            user_id=user_id,
            comment=body.get("comment"),
        )
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/approvals/{approval_id}/reject")
async def reject_approval(
    approval_id: str,
    body: Optional[Dict[str, Any]] = None,
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_current_user),
    _=Depends(require_permission("admin.workflow")),
) -> Dict[str, Any]:
    """Reject a pending approval request."""
    body = body or {}
    try:
        user_id = current_user.get("id", "unknown") if current_user else "system"
        result = await approval_service.reject(
            approval_id=approval_id,
            user_id=user_id,
            comment=body.get("comment"),
        )
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ──────────────────────────────────────────────
# Webhook trigger
# ──────────────────────────────────────────────


@router.post("/webhook/{workflow_id}")
async def webhook_trigger(
    workflow_id: str,
    body: Dict[str, Any],
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_current_user),
) -> Dict[str, Any]:
    """Trigger a workflow via webhook.

    The webhook payload becomes the workflow context.
    HMAC validation is handled by the WebhookTrigger internally.
    """
    try:
        tenant_id = current_user.get("tenant_id") if current_user else None
        result = await workflow_engine.execute_workflow(
            workflow_id=workflow_id,
            trigger_type="webhook",
            trigger_payload=body,
            tenant_id=tenant_id,
            triggered_by="webhook",
        )
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

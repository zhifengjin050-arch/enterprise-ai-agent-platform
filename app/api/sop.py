"""SOP management API routes.

CRUD operations for SOP templates and execution tracking.
"""
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.sop.engine import (
    StepStatus,
    abort_execution,
    create_execution,
    execution_store,
    update_step_status,
)
from app.sop.template import (
    get_sop_by_id,
    list_all_sops,
    search_sops,
    validate_sop_structure,
)
from app.sop.tracker import (
    calculate_sop_stats,
    get_execution_history,
    get_sop_summary,
)

router = APIRouter(prefix="/api/sop", tags=["sop"])


@router.get("/templates")
async def list_sop_templates(search: Optional[str] = Query(None, description="Search query")):
    """List all SOP templates, optionally filtered by search."""
    if search:
        results = search_sops(search)
    else:
        results = list_all_sops()
    return {"templates": [s.to_dict() for s in results], "total": len(results)}


@router.get("/templates/{sop_id}")
async def get_sop_template(sop_id: str):
    """Get a single SOP template by ID."""
    sop = get_sop_by_id(sop_id)
    if not sop:
        raise HTTPException(status_code=404, detail=f"SOP template '{sop_id}' not found")
    return {"template": sop.to_dict()}


@router.post("/templates")
async def create_sop_template(data: dict):
    """Create a new SOP template (validates structure)."""
    errors = validate_sop_structure(data)
    if errors:
        raise HTTPException(status_code=400, detail={"validation_errors": errors})
    # TODO: Persist to database
    return {"message": "SOP template created (placeholder)", "template": data}


@router.post("/execute")
async def start_sop_execution(
    sop_id: str = Query(..., description="SOP template ID"),
    trigger: str = Query("api", description="Execution trigger source"),
    triggered_by: Optional[str] = Query(None, description="Who triggered this"),
):
    """Start executing an SOP procedure."""
    sop = get_sop_by_id(sop_id)
    if not sop:
        raise HTTPException(status_code=404, detail=f"SOP template '{sop_id}' not found")

    execution = create_execution(
        sop_id=sop.id,
        sop_title=sop.title,
        steps=[s.to_dict() for s in sop.steps],
        trigger=trigger,
        triggered_by=triggered_by,
    )
    return {"execution": execution.to_dict()}


@router.get("/executions/{execution_id}")
async def get_execution(execution_id: str):
    """Get the status of an SOP execution."""
    execution = execution_store.get(execution_id)
    if not execution:
        raise HTTPException(status_code=404, detail=f"Execution '{execution_id}' not found")
    return {"execution": execution.to_dict()}


@router.put("/executions/{execution_id}/steps/{step_order}")
async def update_step(
    execution_id: str,
    step_order: int,
    status: str = Query(..., description="Step status: success/failed/skipped"),
    output: Optional[str] = Query(None, description="Step output"),
    error: Optional[str] = Query(None, description="Error message"),
):
    """Update the status of a step in an execution."""
    try:
        step_status = StepStatus(status)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

    execution = update_step_status(
        execution_id=execution_id,
        step_order=step_order,
        status=step_status,
        output=output,
        error=error,
    )
    if not execution:
        raise HTTPException(status_code=404, detail=f"Execution '{execution_id}' not found")
    return {"execution": execution.to_dict()}


@router.post("/executions/{execution_id}/abort")
async def abort_execution_endpoint(execution_id: str):
    """Abort an ongoing SOP execution."""
    execution = abort_execution(execution_id)
    if not execution:
        raise HTTPException(status_code=404, detail=f"Execution '{execution_id}' not found")
    return {"execution": execution.to_dict()}


@router.get("/history")
async def get_history(
    sop_id: Optional[str] = Query(None, description="Filter by SOP ID"),
    days: int = Query(30, description="Days of history"),
    limit: int = Query(20, ge=1, le=100),
):
    """Get SOP execution history."""
    history = get_execution_history(sop_id=sop_id, days=days, limit=limit)
    return {"executions": history, "total": len(history)}


@router.get("/stats/{sop_id}")
async def get_stats(sop_id: str):
    """Get execution statistics for a specific SOP."""
    sop = get_sop_by_id(sop_id)
    if not sop:
        raise HTTPException(status_code=404, detail=f"SOP template '{sop_id}' not found")
    stats = calculate_sop_stats(sop_id)
    return {"sop_id": sop_id, "stats": stats.to_dict()}


@router.get("/summary")
async def get_summary():
    """Get summary of all SOPs with execution stats."""
    return {"summary": get_sop_summary()}

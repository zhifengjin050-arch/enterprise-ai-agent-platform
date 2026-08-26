"""Tests for WorkflowOrchestrator."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.workflow.orchestrator import WorkflowOrchestrator


@pytest.fixture
def orchestrator() -> WorkflowOrchestrator:
    return WorkflowOrchestrator()


@pytest.mark.asyncio
async def test_process_document_success(orchestrator: WorkflowOrchestrator) -> None:
    """process_document should run the pipeline and persist state."""
    with (
        patch.object(orchestrator, "_save_workflow_run") as mock_save,
        patch("app.workflow.orchestrator.knowledge_pipeline") as mock_pipeline,
    ):
        mock_pipeline.ainvoke = AsyncMock(
            return_value={
                "document_id": "doc-001",
                "status": "completed",
                "stored": True,
                "indexed": True,
                "error": None,
                "current_node": "index",
            }
        )

        result = await orchestrator.process_document(
            document_id="doc-001",
            raw_content="# Doc\n\nContent.",
            title="Test Doc",
        )

    assert result["document_id"] == "doc-001"
    assert result["status"] == "completed"
    assert mock_save.call_count == 2


@pytest.mark.asyncio
async def test_process_document_failure(orchestrator: WorkflowOrchestrator) -> None:
    """process_document should handle pipeline failures."""
    with (
        patch.object(orchestrator, "_save_workflow_run"),
        patch("app.workflow.orchestrator.knowledge_pipeline") as mock_pipeline,
    ):
        mock_pipeline.ainvoke = AsyncMock(side_effect=RuntimeError("Pipeline crashed"))

        result = await orchestrator.process_document(
            document_id="doc-002",
            raw_content="# Doc\n\nContent.",
        )

    assert result["status"] == "failed"
    assert "Pipeline crashed" in result["error"]


@pytest.mark.asyncio
async def test_approve_review(orchestrator: WorkflowOrchestrator) -> None:
    """approve_review should set decision=approved and resume pipeline."""
    mock_run = MagicMock()
    mock_run.id = "wf-run-001"
    mock_run.status = "review"
    mock_run.document_id = "doc-001"
    mock_run.state_json = {
        "document_id": "doc-001",
        "need_review": True,
        "status": "review",
        "quality_score": 0.3,
        "quality_issues": ["Too short"],
    }

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_run

    mock_session = MagicMock()
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    with (
        patch(
            "app.workflow.orchestrator.get_session_factory",
            return_value=lambda: mock_session,
        ),
        patch.object(orchestrator, "_save_workflow_run"),
        patch("app.workflow.orchestrator.knowledge_pipeline") as mock_pipeline,
    ):
        mock_pipeline.ainvoke = AsyncMock(
            return_value={
                "document_id": "doc-001",
                "stored": True,
                "indexed": True,
                "status": "completed",
                "error": None,
            }
        )

        result = await orchestrator.approve_review(
            workflow_run_id="wf-run-001",
            comment="Looks good after review.",
        )

    # The result dict may contain "error": None key, so check value not key presence
    assert result.get("error") is None
    assert result["stored"] is True


@pytest.mark.asyncio
async def test_approve_review_not_found(orchestrator: WorkflowOrchestrator) -> None:
    """approve_review should return error if workflow not found."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None

    mock_session = MagicMock()
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    with (
        patch(
            "app.workflow.orchestrator.get_session_factory",
            return_value=lambda: mock_session,
        ),
    ):
        result = await orchestrator.approve_review(workflow_run_id="not-found")

    # For "not found" case, the result dict has "error" as string
    assert isinstance(result.get("error"), str)


@pytest.mark.asyncio
async def test_reject_review(orchestrator: WorkflowOrchestrator) -> None:
    """reject_review should set decision=rejected and mark completed."""
    mock_run = MagicMock()
    mock_run.id = "wf-run-001"
    mock_run.status = "review"
    mock_run.document_id = "doc-001"
    mock_run.state_json = {
        "document_id": "doc-001",
        "need_review": True,
        "status": "review",
        "quality_score": 0.3,
    }

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_run

    mock_session = MagicMock()
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    with (
        patch(
            "app.workflow.orchestrator.get_session_factory",
            return_value=lambda: mock_session,
        ),
        patch.object(orchestrator, "_save_workflow_run"),
    ):
        result = await orchestrator.reject_review(
            workflow_run_id="wf-run-001",
            comment="Insufficient quality.",
        )

    # Reject intentionally sets error with reason
    assert "Rejected" in (result.get("error") or "")
    assert result["review_decision"] == "rejected"
    assert result["status"] == "completed"


@pytest.mark.asyncio
async def test_get_workflow_run(orchestrator: WorkflowOrchestrator) -> None:
    """get_workflow_run should return the workflow record."""
    mock_run = MagicMock()
    mock_run.id = "wf-run-001"
    mock_run.workflow_type = "knowledge"
    mock_run.document_id = "doc-001"
    mock_run.status = "completed"
    mock_run.current_node = "index"
    mock_run.state_json = {"document_id": "doc-001"}
    mock_run.error = None
    now = datetime.now(timezone.utc)
    mock_run.created_at = now
    mock_run.updated_at = now

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_run

    mock_session = MagicMock()
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    with (
        patch(
            "app.workflow.orchestrator.get_session_factory",
            return_value=lambda: mock_session,
        ),
    ):
        result = await orchestrator.get_workflow_run("wf-run-001")

    assert result is not None
    assert result["id"] == "wf-run-001"
    assert result["status"] == "completed"

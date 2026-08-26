"""Tests for KnowledgeState schema and KnowledgeState model."""

from __future__ import annotations

import pytest

from app.workflow.state import KnowledgeState


def test_knowledge_state_structure() -> None:
    """Verify KnowledgeState has the required fields."""
    state: KnowledgeState = {
        "document_id": "doc-001",
        "file_path": "/path/to/doc.md",
        "raw_content": "raw content",
        "markdown_content": "# Title\n\nContent",
        "title": "Test Document",
        "doc_type": "sop",
        "tags": ["k8s", "docker"],
        "quality_score": 0.85,
        "quality_issues": [],
        "embedding_id": "emb_doc-001_dim3",
        "stored": True,
        "indexed": True,
        "need_review": False,
        "review_decision": None,
        "review_comment": None,
        "status": "completed",
        "current_node": "index",
        "error": None,
        "metadata": {"author": "tester"},
    }
    assert state["document_id"] == "doc-001"
    assert state["doc_type"] == "sop"
    assert state["tags"] == ["k8s", "docker"]
    assert state["quality_score"] == 0.85
    assert state["stored"] is True
    assert state["indexed"] is True
    assert state["need_review"] is False
    assert state["status"] == "completed"


def test_knowledge_state_no_chat_fields() -> None:
    """Ensure no question/answer/chat_history/conversation fields exist."""
    state: KnowledgeState = {
        "document_id": "doc-001",
    }
    # These fields must NOT be present
    assert "question" not in state
    assert "answer" not in state
    assert "chat_history" not in state
    assert "conversation" not in state


def test_knowledge_state_minimal() -> None:
    """Minimal state should still be valid."""
    state: KnowledgeState = {
        "document_id": "doc-001",
        "raw_content": "",
        "title": None,
        "tags": [],
        "quality_score": 0.0,
        "quality_issues": [],
        "stored": False,
        "indexed": False,
        "need_review": False,
        "status": "pending",
        "metadata": {},
    }
    assert state["status"] == "pending"


@pytest.mark.parametrize(
    "status",
    ["pending", "processing", "review", "completed", "failed"],
)
def test_knowledge_state_valid_statuses(status: str) -> None:
    """All valid statuses should be accepted."""
    state: KnowledgeState = {
        "document_id": "doc-001",
        "status": status,
        "tags": [],
        "quality_score": 0.0,
        "quality_issues": [],
        "stored": False,
        "indexed": False,
        "need_review": False,
        "metadata": {},
    }
    assert state["status"] == status


def test_knowledge_state_empty_metadata() -> None:
    """metadata defaults to empty dict."""
    state: KnowledgeState = {
        "document_id": "doc-001",
    }
    assert state.get("metadata", {}) == {}


def test_knowledge_state_workflow_run_id() -> None:
    """workflow_run_id should be optional."""
    state: KnowledgeState = {
        "document_id": "doc-001",
    }
    # Should not raise, workflow_run_id is optional via TypedDict total=False
    state["workflow_run_id"] = "wf-run-001"
    assert state["workflow_run_id"] == "wf-run-001"

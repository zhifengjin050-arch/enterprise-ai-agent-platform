"""Tests for the human-in-the-loop review flow."""

from __future__ import annotations

import pytest

from app.workflow.knowledge_pipeline import review_node, review_router


@pytest.mark.asyncio
async def test_review_node_sets_need_review() -> None:
    """review_node should set need_review=True and status='review'."""
    state = {
        "document_id": "doc-001",
        "quality_score": 0.3,
        "quality_issues": ["Content too short"],
    }
    result = await review_node(state)
    assert result.get("need_review") is True
    assert result.get("status") == "review"
    assert result.get("current_node") == "review"
    assert result.get("review_decision") is None


@pytest.mark.asyncio
async def test_review_node_preserves_issues() -> None:
    """review_node should carry forward quality_issues."""
    state = {
        "document_id": "doc-002",
        "quality_score": 0.2,
        "quality_issues": ["Too short", "No headings"],
    }
    result = await review_node(state)
    assert "Too short" in result.get("quality_issues", [])
    assert "No headings" in result.get("quality_issues", [])


def test_review_router_approved_goes_to_embed() -> None:
    """When review_decision='approved', route to 'embed'."""
    state = {"review_decision": "approved"}
    assert review_router(state) == "embed"


def test_review_router_rejected_goes_to_end() -> None:
    """When review_decision='rejected', route to END."""
    state = {"review_decision": "rejected"}
    assert review_router(state) == "__end__"


def test_review_router_no_decision_goes_to_end() -> None:
    """When no decision made yet, stay at end (no forward progress)."""
    state = {"review_decision": None}
    assert review_router(state) == "__end__"


def test_review_router_default() -> None:
    """Default state with no review_decision routes to END."""
    state = {}
    assert review_router(state) == "__end__"
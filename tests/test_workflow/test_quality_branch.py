"""Tests for quality_node scoring and conditional routing.

Nodes are now async (support LLM fallback). All tests use pytest.mark.asyncio.
"""

from __future__ import annotations

import pytest

from app.workflow.knowledge_pipeline import quality_node, quality_router

# ── quality_node scoring ─────────────────────────────────


@pytest.mark.asyncio
async def test_quality_high_score() -> None:
    """Long, well-structured content should score >= 0.5."""
    state = {
        "document_id": "doc-001",
        "markdown_content": (
            "# Introduction\n\n"
            "This is a comprehensive document with multiple sections.\n\n"
            "## Section 1\n\nDetailed content here.\n\n"
            "## Section 2\n\nMore detailed content.\n\n"
            "## Section 3\n\nEven more content.\n\n"
            "- List item 1\n"
            "- List item 2\n"
        ),
        "title": "Comprehensive Guide",
    }
    result = await quality_node(state)
    score = result.get("quality_score", 0.0)
    assert score >= 0.5, f"Expected >= 0.5, got {score}"


@pytest.mark.asyncio
async def test_quality_low_score_short() -> None:
    """Very short content should score < 0.5."""
    state = {
        "document_id": "doc-002",
        "markdown_content": "Short.",
        "title": "Untitled",
    }
    result = await quality_node(state)
    score = result.get("quality_score", 0.0)
    assert score < 0.5, f"Expected < 0.5, got {score}"
    assert len(result.get("quality_issues", [])) > 0


@pytest.mark.asyncio
async def test_quality_low_score_no_title() -> None:
    """Untitled document with brief content should score < 0.5."""
    state = {
        "document_id": "doc-003",
        "markdown_content": "# A\n\nSome brief notes.",
        "title": "Untitled",
    }
    result = await quality_node(state)
    score = result.get("quality_score", 0.0)
    issues = result.get("quality_issues", [])
    assert any("title" in i.lower() for i in issues)


@pytest.mark.asyncio
async def test_quality_no_headings_issue() -> None:
    """Content without markdown headings should mention structure issue."""
    state = {
        "document_id": "doc-004",
        "markdown_content": "Plain text without any markdown headings or lists.",
        "title": "Plain Document",
    }
    result = await quality_node(state)
    issues = result.get("quality_issues", [])
    assert any("headings" in i.lower() for i in issues)


@pytest.mark.asyncio
async def test_quality_todo_marker() -> None:
    """Content with TODO markers should flag validity issue."""
    state = {
        "document_id": "doc-005",
        "markdown_content": "# Draft\n\nTODO: fill in details later.",
        "title": "Draft Doc",
    }
    result = await quality_node(state)
    issues = result.get("quality_issues", [])
    assert any("TODO" in i or "placeholder" in i.lower() for i in issues)


@pytest.mark.asyncio
async def test_quality_empty_content() -> None:
    """Empty content should yield score < 0.1 (very low)."""
    state = {
        "document_id": "doc-006",
        "markdown_content": "",
        "title": "Empty",
    }
    result = await quality_node(state)
    score = result.get("quality_score", 1.0)
    assert score < 0.1, f"Expected score < 0.1, got {score}"
    assert len(result.get("quality_issues", [])) > 0


# ── quality_router conditional branching ──────────────────


def test_router_high_quality_goes_to_entity_extract() -> None:
    """Score >= 0.5 routes to 'entity_extract'."""
    state = {"quality_score": 0.7}
    assert quality_router(state) == "entity_extract"


def test_router_low_quality_goes_to_review() -> None:
    """Score < 0.5 routes to 'review'."""
    state = {"quality_score": 0.3}
    assert quality_router(state) == "review"


def test_router_exactly_0_5_goes_to_entity_extract() -> None:
    """Score exactly 0.5 should route to 'entity_extract'."""
    state = {"quality_score": 0.5}
    assert quality_router(state) == "entity_extract"


def test_router_default_zero() -> None:
    """Default score of 0.0 routes to 'review'."""
    state = {}
    assert quality_router(state) == "review"


@pytest.mark.parametrize(
    "score,expected",
    [
        (1.0, "entity_extract"),
        (0.9, "entity_extract"),
        (0.5, "entity_extract"),
        (0.49, "review"),
        (0.0, "review"),
        (-0.1, "review"),
    ],
)
def test_router_parametrized(score: float, expected: str) -> None:
    state = {"quality_score": score}
    assert quality_router(state) == expected

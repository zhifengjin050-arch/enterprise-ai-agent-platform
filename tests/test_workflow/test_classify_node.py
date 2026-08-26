"""Tests for classify_node in the knowledge pipeline.

Nodes are now async (support LLM fallback). All tests use pytest.mark.asyncio.
"""

from __future__ import annotations

import pytest

from app.workflow.knowledge_pipeline import classify_node


@pytest.mark.asyncio
async def test_classify_sop() -> None:
    """Should classify content with SOP keywords as 'sop'."""
    state = {
        "document_id": "doc-001",
        "markdown_content": "This is a Standard Operating Procedure for deployment.",
        "title": "Deployment SOP",
    }
    result = await classify_node(state)
    assert result["doc_type"] == "sop"


@pytest.mark.asyncio
async def test_classify_incident() -> None:
    """Should classify content with incident keywords as 'incident'."""
    state = {
        "document_id": "doc-002",
        "markdown_content": "Postmortem analysis of production outage incident.",
        "title": "Incident Report",
    }
    result = await classify_node(state)
    assert result["doc_type"] == "incident"


@pytest.mark.asyncio
async def test_classify_architecture() -> None:
    """Should classify content with architecture keywords."""
    state = {
        "document_id": "doc-003",
        "markdown_content": "System architecture design for microservices.",
        "title": "Architecture Overview",
    }
    result = await classify_node(state)
    assert result["doc_type"] == "architecture"


@pytest.mark.asyncio
async def test_classify_configuration() -> None:
    """Should classify content with config/deploy keywords."""
    state = {
        "document_id": "doc-004",
        "markdown_content": "Server deployment configuration guide.",
        "title": "Deployment Config",
    }
    result = await classify_node(state)
    assert result["doc_type"] == "configuration"


@pytest.mark.asyncio
async def test_classify_best_practice() -> None:
    """Should classify content with best practice keywords."""
    state = {
        "document_id": "doc-005",
        "markdown_content": "Best practices for Kubernetes security.",
        "title": "Security Best Practices",
    }
    result = await classify_node(state)
    assert result["doc_type"] == "best_practice"


@pytest.mark.asyncio
async def test_classify_default_other() -> None:
    """When no keywords match, default to 'other'."""
    state = {
        "document_id": "doc-006",
        "markdown_content": "Some random documentation text.",
        "title": "General Notes",
    }
    result = await classify_node(state)
    assert result["doc_type"] == "other"


@pytest.mark.asyncio
async def test_classify_chinese_keywords() -> None:
    """Should correctly classify content with Chinese keywords."""
    state = {
        "document_id": "doc-007",
        "markdown_content": "故障排查步骤：当服务宕机时执行以下操作流程。",
        "title": "故障处理",
    }
    result = await classify_node(state)
    # The rule_classifier matches 步骤/操作流程 → sop, 故障 → incident
    # SOP has more matches here so it should be sop
    assert result["doc_type"] == "sop"


@pytest.mark.asyncio
async def test_classify_empty_content() -> None:
    """Should handle empty content gracefully."""
    state = {
        "document_id": "doc-008",
        "markdown_content": "",
        "title": "",
    }
    result = await classify_node(state)
    assert result["doc_type"] == "other"


@pytest.mark.asyncio
async def test_classify_error_handling() -> None:
    """Exception in classify_node should return error."""
    state: dict = {}
    result = await classify_node(state)
    # Should still work since we use .get() with defaults
    assert "doc_type" in result

"""Tests for Knowledge Graph enhanced agent.

Tests that the agent works correctly with graph expansion enabled.
"""
from __future__ import annotations

from typing import Any, Dict, List
from unittest.mock import AsyncMock

import pytest

from app.agent.knowledge_agent import KnowledgeAgent, KnowledgeAgentResult
from app.search.hybrid import HybridResult


class MockHybridSearch:
    """Mock HybridSearch for testing."""

    def __init__(self, results: List[HybridResult]):
        self._results = results

    async def search(self, query: str, top_k: int = 10, **kwargs):
        return self._results


def make_result(doc_id: str, title: str, snippet: str, score: float) -> HybridResult:
    """Create a mock HybridResult."""
    return HybridResult(
        id=doc_id, title=title, snippet=snippet, score=score,
        metadata={"doc_type": "sop"},
    )


class TestGraphEnhancedAgent:
    """Tests for KnowledgeAgent with graph expansion."""

    @pytest.mark.asyncio
    async def test_ask_with_graph_expansion(self) -> None:
        """Agent should still work with graph expansion when DB is empty."""
        mock_llm = AsyncMock()
        async def mock_structured_output(prompt: str, schema: Dict[str, Any], **kwargs):
            return {
                "answer": "这是一个关于支付服务的测试回答。",
                "confidence": 0.85,
                "reasoning_summary": "Test",
                "used_sources": ["支付服务SOP"],
            }
        mock_llm.structured_output = mock_structured_output

        mock_search = MockHybridSearch([
            make_result("1", "支付服务SOP", "支付服务流程", 0.9),
        ])

        agent = KnowledgeAgent(llm_client=mock_llm, hybrid_search=mock_search)
        result = await agent.ask(query="支付失败怎么排查")

        assert isinstance(result, KnowledgeAgentResult)
        assert result.answer
        assert result.conversation_id
        assert result.confidence == 0.85

    @pytest.mark.asyncio
    async def test_graph_expansion_graceful_fallback(self) -> None:
        """Graph expansion failure should not break the agent."""
        mock_llm = AsyncMock()
        async def mock_structured_output(*args, **kwargs):
            return {
                "answer": "测试回答",
                "confidence": 0.7,
                "reasoning_summary": "",
                "used_sources": [],
            }
        mock_llm.structured_output = mock_structured_output

        agent = KnowledgeAgent(llm_client=mock_llm,
                                hybrid_search=MockHybridSearch([]))
        result = await agent.ask(query="测试查询")
        assert result.answer
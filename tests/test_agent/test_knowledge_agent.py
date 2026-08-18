"""Tests for the KnowledgeAgent end-to-end pipeline.

Tests the full ask() flow including intent classification, query rewriting,
hybrid search, context building, answer generation, and citation extraction.
"""
from __future__ import annotations

from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agent.knowledge_agent import KnowledgeAgent, KnowledgeAgentResult
from app.search.hybrid import HybridResult


class MockHybridSearch:
    """Mock HybridSearch for testing."""

    def __init__(self, results: List[HybridResult]):
        self._results = results

    async def search(self, query: str, top_k: int = 10, **kwargs):
        return self._results


def make_mock_result(
    doc_id: str,
    title: str,
    snippet: str,
    score: float,
) -> HybridResult:
    """Create a mock HybridResult."""
    return HybridResult(
        id=doc_id,
        title=title,
        snippet=snippet,
        score=score,
        metadata={"doc_type": "sop"},
    )


class TestKnowledgeAgent:
    """Tests for the end-to-end KnowledgeAgent."""

    @pytest.mark.asyncio
    async def test_ask_normal_qa(self) -> None:
        """Normal Q&A should return complete result."""
        mock_llm = AsyncMock()
        async def mock_structured_output(prompt: str, schema: Dict[str, Any], **kwargs):
            return {
                "answer": "Nginx 502通常由于upstream不可用导致，检查后端服务状态。",
                "confidence": 0.85,
                "reasoning_summary": "Matched Nginx故障处理SOP",
                "used_sources": ["Nginx故障处理SOP"],
            }
        mock_llm.structured_output = mock_structured_output

        mock_search = MockHybridSearch([
            make_mock_result("1", "Nginx故障处理SOP", "502表示上游服务异常", 0.93),
            make_mock_result("2", "Kubernetes部署指南", "Pod部署步骤", 0.45),
        ])

        agent = KnowledgeAgent(
            llm_client=mock_llm,
            hybrid_search=mock_search,
        )
        result = await agent.ask(query="nginx 502怎么排查")

        assert isinstance(result, KnowledgeAgentResult)
        assert "Nginx 502" in result.answer
        assert result.confidence == 0.85
        assert len(result.citations) > 0
        assert result.conversation_id

    @pytest.mark.asyncio
    async def test_ask_no_search_results(self) -> None:
        """No search results should still produce answer."""
        mock_llm = AsyncMock()
        async def mock_structured_output(prompt: str, schema: Dict[str, Any], **kwargs):
            return {
                "answer": "未找到相关文档，请尝试其他关键词。",
                "confidence": 0.1,
                "reasoning_summary": "No results from search",
                "used_sources": [],
            }
        mock_llm.structured_output = mock_structured_output

        mock_search = MockHybridSearch([])

        agent = KnowledgeAgent(llm_client=mock_llm, hybrid_search=mock_search)
        result = await agent.ask(query="不存在的知识")
        assert result.answer
        assert result.sources == []

    @pytest.mark.asyncio
    async def test_ask_llm_failure_fallback(self) -> None:
        """LLM failure should return graceful fallback."""
        mock_llm = AsyncMock()
        async def mock_fail(*args, **kwargs):
            raise ConnectionError("API unavailable")
        mock_llm.structured_output = mock_fail

        mock_search = MockHybridSearch([
            make_mock_result("1", "运维手册", "配置说明", 0.8),
        ])

        agent = KnowledgeAgent(llm_client=mock_llm, hybrid_search=mock_search)
        result = await agent.ask(query="配置说明")
        assert "暂时不可用" in result.answer or result.answer
        assert result.conversation_id

    @pytest.mark.asyncio
    async def test_ask_with_conversation_id(self) -> None:
        """Providing conversation_id should continue existing conversation."""
        mock_llm = AsyncMock()
        async def mock_structured_output(prompt: str, schema: Dict[str, Any], **kwargs):
            return {
                "answer": "测试回答",
                "confidence": 0.8,
                "reasoning_summary": "test",
                "used_sources": [],
            }
        mock_llm.structured_output = mock_structured_output
        mock_search = MockHybridSearch([])

        agent = KnowledgeAgent(llm_client=mock_llm, hybrid_search=mock_search)
        result1 = await agent.ask(query="问题1")
        conv_id = result1.conversation_id

        result2 = await agent.ask(query="问题2", conversation_id=conv_id)
        assert result2.conversation_id == conv_id

    @pytest.mark.asyncio
    async def test_ask_intent_is_set(self) -> None:
        """Result should have intent field populated."""
        mock_llm = AsyncMock()
        async def mock_structured_output(*args, **kwargs):
            return {
                "answer": "test",
                "confidence": 0.5,
                "reasoning_summary": "test",
                "used_sources": [],
            }
        mock_llm.structured_output = mock_structured_output
        mock_search = MockHybridSearch([])

        agent = KnowledgeAgent(llm_client=mock_llm, hybrid_search=mock_search)
        result = await agent.ask(query="502故障")
        assert result.intent == "incident_analysis"

    @pytest.mark.asyncio
    async def test_ask_citations_generated(self) -> None:
        """Citations should be generated from search results."""
        mock_llm = AsyncMock()
        async def mock_structured_output(prompt: str, schema: Dict[str, Any], **kwargs):
            return {
                "answer": "测试回答",
                "confidence": 0.9,
                "reasoning_summary": "test",
                "used_sources": ["文档A", "文档B"],
            }
        mock_llm.structured_output = mock_structured_output

        mock_search = MockHybridSearch([
            make_mock_result("a", "文档A", "内容A", 0.95),
            make_mock_result("b", "文档B", "内容B", 0.85),
            make_mock_result("c", "文档C", "内容C", 0.50),
        ])

        agent = KnowledgeAgent(llm_client=mock_llm, hybrid_search=mock_search)
        result = await agent.ask(query="测试")
        assert len(result.citations) > 0
        assert result.citations[0].score >= result.citations[-1].score

    @pytest.mark.asyncio
    async def test_conversation_saved(self) -> None:
        """Messages should be saved to conversation history."""
        mock_llm = AsyncMock()
        async def mock_structured_output(*args, **kwargs):
            return {
                "answer": "回答",
                "confidence": 0.8,
                "reasoning_summary": "",
                "used_sources": [],
            }
        mock_llm.structured_output = mock_structured_output

        agent = KnowledgeAgent(llm_client=mock_llm, hybrid_search=MockHybridSearch([]))
        result = await agent.ask(query="问题")

        from app.conversation.memory import memory
        conv = memory.get_conversation(result.conversation_id)
        assert conv is not None
        assert len(conv.messages) >= 2  # user + assistant

    def test_to_dict_serialization(self) -> None:
        """KnowledgeAgentResult.to_dict should serialize correctly."""
        from app.citation.models import CitationSource

        result = KnowledgeAgentResult(
            answer="测试答案",
            citations=[
                CitationSource(
                    document_id="doc1", title="文档1",
                    content_snippet="内容", score=0.9,
                )
            ],
            confidence=0.85,
            sources=["文档1"],
            conversation_id="conv-1",
            intent="sop_lookup",
        )
        d = result.to_dict()
        assert d["answer"] == "测试答案"
        assert len(d["citations"]) == 1
        assert d["confidence"] == 0.85
        assert d["sources"] == ["文档1"]
        assert d["conversation_id"] == "conv-1"
        assert d["intent"] == "sop_lookup"
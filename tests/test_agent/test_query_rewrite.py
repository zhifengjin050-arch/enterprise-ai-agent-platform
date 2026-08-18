"""Tests for query rewriting service.

Tests rule-based synonym expansion and LLM fallback for query rewriting.
"""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.query.rewrite import QueryRewriteService, RewriteResult, _rule_rewrite


class TestRuleRewrite:
    """Tests for the first-layer rule-based query rewriting."""

    def test_nginx_synonym_expansion(self) -> None:
        """Query containing "nginx" should include related terms."""
        result = _rule_rewrite("nginx挂了", "incident_analysis")
        assert len(result) >= 1
        assert any("nginx error" in q for q in result)
        assert any("nginx troubleshooting" in q for q in result)

    def test_502_synonym_expansion(self) -> None:
        """Query containing "502" should include related terms."""
        result = _rule_rewrite("502错误排查", "incident_analysis")
        assert any("502 bad gateway" in q.lower() for q in result)
        assert any("bad gateway" in q.lower() for q in result)

    def test_kubernetes_synonym_expansion(self) -> None:
        """Query containing "kubernetes" should include k8s variants."""
        result = _rule_rewrite("kubernetes pod挂了", "incident_analysis")
        assert any("k8s" in q for q in result)
        assert any("kubectl" in q for q in result)

    def test_crashloopbackoff_expansion(self) -> None:
        """Query containing "CrashLoopBackOff" should expand."""
        result = _rule_rewrite("如何处理CrashLoopBackOff", "sop_lookup")
        assert any("CrashLoopBackOff" in q for q in result)
        assert len(result) >= 1

    def test_intent_template(self) -> None:
        """Intent-based templates should be applied."""
        result = _rule_rewrite("nginx配置", "configuration_help")
        assert any("配置指南" in q for q in result)
        assert any("configuration" in q for q in result)

    def test_dedup(self) -> None:
        """Rewritten queries should not contain duplicates."""
        result = _rule_rewrite("nginx", "general_search")
        assert len(result) == len(set(result))

    def test_no_match(self) -> None:
        """Query with no known terms should return only the original."""
        result = _rule_rewrite("hello world", "general_search")
        assert len(result) == 1
        assert result[0] == "hello world"


class TestQueryRewriteService:
    """Tests for QueryRewriteService with optional LLM fallback."""

    @pytest.mark.asyncio
    async def test_rewrite_rule_only(self) -> None:
        """Rewrite should work with rule-based only."""
        service = QueryRewriteService()
        result = await service.rewrite("nginx挂了", "incident_analysis")
        assert isinstance(result, RewriteResult)
        assert result.original_query == "nginx挂了"
        assert len(result.rewritten_queries) >= 1

    @pytest.mark.asyncio
    async def test_rewrite_with_llm_fallback(self) -> None:
        """LLM fallback should add more variants."""
        mock_llm = AsyncMock()
        async def mock_structured_output(*args, **kwargs):
            return {"variants": ["nginx 502排查步骤", "nginx upstream故障处理"]}
        mock_llm.structured_output = mock_structured_output

        service = QueryRewriteService(llm_client=mock_llm)
        result = await service.rewrite(
            "nginx挂了 如何排查故障", "incident_analysis"
        )
        assert len(result.rewritten_queries) >= 1
        assert result.original_query == "nginx挂了 如何排查故障"

    @pytest.mark.asyncio
    async def test_llm_fallback_failure(self) -> None:
        """LLM failure should not break rewrite."""
        mock_llm = AsyncMock()
        async def mock_fail(*args, **kwargs):
            raise ConnectionError("API unreachable")
        mock_llm.structured_output = mock_fail

        service = QueryRewriteService(llm_client=mock_llm)
        result = await service.rewrite(
            "redis挂了 怎么排查", "incident_analysis"
        )
        # Should still have rule-based results
        assert len(result.rewritten_queries) >= 1


class TestRewriteResult:
    """Tests for RewriteResult dataclass."""

    def test_rewrite_result_fields(self) -> None:
        """RewriteResult should store all fields."""
        result = RewriteResult(
            original_query="nginx挂了",
            rewritten_queries=[
                "nginx挂了",
                "nginx 502 bad gateway",
                "nginx error log",
            ],
        )
        assert result.original_query == "nginx挂了"
        assert len(result.rewritten_queries) == 3
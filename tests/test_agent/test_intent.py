"""Tests for query intent classification.

Tests rule-based intent recognition with various query patterns.
"""

from __future__ import annotations

from app.query.intent import QueryIntent, classify_intent


class TestClassifyIntent:
    """Tests for the rule-based intent classifier."""

    def test_incident_analysis_downtime(self) -> None:
        """Query mentioning "挂了" should classify as incident_analysis."""
        result = classify_intent("nginx挂了", use_llm_fallback=False)
        assert result.intent == "incident_analysis"
        assert result.confidence >= 0.3

    def test_incident_analysis_error(self) -> None:
        """Query mentioning "502" should classify as incident_analysis."""
        result = classify_intent("数据库连接超时", use_llm_fallback=False)
        assert result.intent == "incident_analysis"
        assert result.original_query == "数据库连接超时"

    def test_sop_lookup_howto(self) -> None:
        """Query with "如何" should classify as sop_lookup."""
        result = classify_intent("如何部署Kubernetes集群", use_llm_fallback=False)
        assert result.intent == "sop_lookup"
        assert result.confidence >= 0.3

    def test_sop_lookup_troubleshoot(self) -> None:
        """Query with "排查" should classify as sop_lookup."""
        result = classify_intent("怎么排查Pod CrashLoopBackOff", use_llm_fallback=False)
        assert result.intent == "sop_lookup"

    def test_architecture_question(self) -> None:
        """Query with "架构" should classify as architecture_question."""
        result = classify_intent("微服务架构设计要点", use_llm_fallback=False)
        assert result.intent == "architecture_question"

    def test_configuration_help(self) -> None:
        """Query with "配置参数" should classify as configuration_help."""
        result = classify_intent("nginx配置参数调优", use_llm_fallback=False)
        assert result.intent == "configuration_help"

    def test_general_search_fallback(self) -> None:
        """Query with no matching keywords should fallback to general_search."""
        result = classify_intent("今天天气真好 sunny day", use_llm_fallback=False)
        assert result.intent == "general_search"

    def test_empty_query(self) -> None:
        """Empty query should return general_search."""
        result = classify_intent("", use_llm_fallback=False)
        assert result.intent == "general_search"

    def test_query_intent_dataclass(self) -> None:
        """QueryIntent should store all fields correctly."""
        intent = QueryIntent(
            intent="incident_analysis",
            confidence=0.91,
            original_query="redis挂了",
        )
        assert intent.intent == "incident_analysis"
        assert intent.confidence == 0.91
        assert intent.original_query == "redis挂了"

    def test_multiple_keywords_higher_confidence(self) -> None:
        """More keyword matches should yield higher confidence."""
        result_multi = classify_intent("502故障排查步骤", use_llm_fallback=False)
        result_single = classify_intent("今天天气", use_llm_fallback=False)
        assert result_multi.confidence > result_single.confidence

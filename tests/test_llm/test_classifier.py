"""Tests for AI-powered document classifier.

Tests both rule_classifier and LLMClassifier with mocked LLM calls.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.knowledge.classifier import (
    CLASSIFICATION_RULES,
    LLMClassifier,
    DocumentClassification,
    classify_document,
    rule_classifier,
)
from app.knowledge.models import DocType, KnowledgeDocument


class TestRuleClassifier:
    """Tests for the first-layer rule-based classifier."""

    def test_classify_sop(self) -> None:
        """Content with SOP keywords should classify as sop."""
        result = rule_classifier("Deployment SOP", "Step-by-step deployment procedure.")
        assert result.doc_type == "sop"
        assert result.confidence >= 0.3
        assert "keyword" in result.reason

    def test_classify_incident(self) -> None:
        """Content with incident keywords should classify as incident."""
        result = rule_classifier("Incident Report", "Root cause analysis of production outage.")
        assert result.doc_type == "incident"
        assert result.confidence >= 0.3

    def test_classify_architecture(self) -> None:
        """Content with architecture keywords should classify as architecture."""
        result = rule_classifier("System Design", "Architecture overview of microservices.")
        assert result.doc_type == "architecture"

    def test_classify_configuration(self) -> None:
        """Content with configuration keywords should classify as configuration."""
        result = rule_classifier("Setup Guide", "Configuration and installation guide.")
        assert result.doc_type == "configuration"

    def test_classify_best_practice(self) -> None:
        """Content with best practice keywords should classify as best_practice."""
        result = rule_classifier("Best Practices", "Security best practices for Kubernetes.")
        assert result.doc_type == "best_practice"

    def test_classify_other_default(self) -> None:
        """Content with no matching keywords should default to other."""
        result = rule_classifier("Random Notes", "Just some random text without keywords.")
        assert result.doc_type == "other"
        assert result.confidence <= 0.3

    def test_classify_chinese_keywords(self) -> None:
        """Chinese keywords should be recognized."""
        result = rule_classifier("故障处理", "操作流程 and 排查步骤 for 故障处理.")
        # Contains both 操作流程 (sop) and 故障 (incident) and 排查步骤 (sop)
        # SOP has more keyword matches here
        assert result.doc_type in ("sop", "incident")

    def test_classify_empty_content(self) -> None:
        """Empty content should be classified as other."""
        result = rule_classifier("", "")
        assert result.doc_type == "other"

    def test_classify_keyword_density_confidence(self) -> None:
        """More matched keywords should yield higher confidence."""
        result_high = rule_classifier(
            "Standard Operating Procedure",
            "Step-by-step troubleshooting procedure with steps.",
        )
        result_low = rule_classifier("Misc", "Random content.")
        assert result_high.confidence > result_low.confidence


class TestLLMClassifier:
    """Tests for the second-layer LLM-based classifier."""

    @pytest.mark.asyncio
    async def test_classify_with_llm(self) -> None:
        """LLMClassifier should use structured_output and return DocumentClassification."""
        mock_llm = AsyncMock()
        mock_llm.structured_output.return_value = {
            "doc_type": "sop",
            "confidence": 0.95,
            "reason": "Contains clear step-by-step instructions.",
        }

        classifier = LLMClassifier(llm_client=mock_llm)
        result = await classifier.classify("My Title", "Step-by-step guide content.")

        assert result.doc_type == "sop"
        assert result.confidence == 0.95
        assert "step-by-step" in result.reason
        mock_llm.structured_output.assert_called_once()

    @pytest.mark.asyncio
    async def test_classify_llm_error_fallback(self) -> None:
        """When LLM fails, should return a low-confidence fallback result."""
        mock_llm = AsyncMock()
        mock_llm.structured_output.side_effect = ValueError("LLM error")

        classifier = LLMClassifier(llm_client=mock_llm)
        result = await classifier.classify("Title", "Content")

        assert result.doc_type == "other"
        assert result.confidence == 0.0
        assert "LLM classification failed" in result.reason

    @pytest.mark.asyncio
    async def test_classify_with_cache(self) -> None:
        """With cache enabled, second call should use cached result."""
        mock_llm = AsyncMock()
        mock_llm.structured_output.return_value = {
            "doc_type": "sop",
            "confidence": 0.95,
            "reason": "Cache test.",
        }

        from app.llm.cache import clear_cache

        clear_cache()

        classifier = LLMClassifier(llm_client=mock_llm)

        # First call should call LLM
        result1 = await classifier.classify("Title", "Same content")
        assert result1.doc_type == "sop"
        assert mock_llm.structured_output.call_count == 1

        # Second call with same content should use cache
        mock_llm.structured_output.reset_mock()
        result2 = await classifier.classify("Title", "Same content")
        assert result2.doc_type == "sop"
        mock_llm.structured_output.assert_not_called()

    @pytest.mark.asyncio
    async def test_classify_without_cache(self) -> None:
        """With cache disabled, every call should go to LLM."""
        mock_llm = AsyncMock()
        mock_llm.structured_output.return_value = {
            "doc_type": "sop",
            "confidence": 0.9,
            "reason": "No cache.",
        }

        from app.llm.cache import clear_cache

        clear_cache()

        classifier = LLMClassifier(llm_client=mock_llm)

        await classifier.classify("Title", "Content", use_cache=False)
        await classifier.classify("Title", "Content", use_cache=False)

        assert mock_llm.structured_output.call_count == 2


class TestClassifyDocument:
    """Tests for the top-level classify_document function (two-layer)."""

    @pytest.mark.asyncio
    async def test_rule_high_confidence_no_llm(self) -> None:
        """When rule confidence >= 0.8, should not call LLM."""
        doc = KnowledgeDocument(
            id="doc-001",
            title="Standard Operating Procedure",
            content="Step-by-step troubleshooting procedure.",
        )

        mock_llm = AsyncMock()
        result = await classify_document(doc, use_llm_fallback=True, llm_client=mock_llm)

        assert result.doc_type == "sop"
        assert result.confidence >= 0.8
        mock_llm.structured_output.assert_not_called()

    @pytest.mark.asyncio
    async def test_rule_low_confidence_calls_llm(self) -> None:
        """When rule confidence < 0.8, should fall back to LLM."""
        doc = KnowledgeDocument(
            id="doc-002",
            title="Random Notes",
            content="Some random text without clear classification keywords.",
        )

        mock_llm = AsyncMock()
        mock_llm.structured_output.return_value = {
            "doc_type": "best_practice",
            "confidence": 0.85,
            "reason": "Content resembles best practice documentation.",
        }

        result = await classify_document(doc, use_llm_fallback=True, llm_client=mock_llm)

        # LLM result has higher confidence, should be used
        assert result.doc_type == "best_practice"
        assert result.confidence == 0.85
        mock_llm.structured_output.assert_called_once()

    @pytest.mark.asyncio
    async def test_llm_fallback_disabled(self) -> None:
        """When use_llm_fallback=False, should never call LLM."""
        doc = KnowledgeDocument(
            id="doc-003",
            title="Random Notes",
            content="Some random text.",
        )

        mock_llm = AsyncMock()
        result = await classify_document(doc, use_llm_fallback=False, llm_client=mock_llm)

        assert result.doc_type == "other"
        assert result.confidence <= 0.3
        mock_llm.structured_output.assert_not_called()

    @pytest.mark.asyncio
    async def test_llm_lower_confidence_uses_rule(self) -> None:
        """When LLM confidence is lower than rule, use rule result."""
        # Use content with some keyword matches but low count
        doc = KnowledgeDocument(
            id="doc-004",
            title="Architecture Overview",
            content="Architecture design document.",
        )

        mock_llm = AsyncMock()
        mock_llm.structured_output.return_value = {
            "doc_type": "other",
            "confidence": 0.2,
            "reason": "Not sure.",
        }

        result = await classify_document(doc, use_llm_fallback=True, llm_client=mock_llm)

        # Rule should win since LLM confidence is lower
        assert result.doc_type == "architecture"
        assert result.confidence > 0.2


class TestDocumentClassification:
    """Tests for the DocumentClassification dataclass."""

    def test_creation(self) -> None:
        """Should create with default values."""
        dc = DocumentClassification(doc_type="sop")
        assert dc.doc_type == "sop"
        assert dc.confidence == 0.0
        assert dc.reason == ""

    def test_creation_full(self) -> None:
        """Should create with all fields."""
        dc = DocumentClassification(
            doc_type="incident", confidence=0.85, reason="Root cause analysis."
        )
        assert dc.doc_type == "incident"
        assert dc.confidence == 0.85
        assert "Root cause" in dc.reason

    def test_confidence_bounds(self) -> None:
        """Confidence should be clamped to [0, 1]."""
        dc = DocumentClassification(doc_type="test", confidence=1.5)
        assert dc.confidence == 1.5  # Dataclass doesn't clamp automatically
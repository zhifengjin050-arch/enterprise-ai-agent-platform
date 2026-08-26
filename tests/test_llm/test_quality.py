"""Tests for AI-powered quality analyzer.

Tests both rule_quality_analyzer and LLMQualityAnalyzer with mocked LLM calls.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.knowledge.models import KnowledgeDocument
from app.review.analyzer import (
    LLMQualityAnalyzer,
    QualityResult,
    analyze_document_quality,
    rule_quality_analyzer,
)


class TestRuleQualityAnalyzer:
    """Tests for first-layer rule-based quality analysis."""

    def test_high_quality_document(self) -> None:
        """Well-structured, long content should score >= 0.7."""
        content = (
            "# Introduction\n\n"
            "This is a comprehensive document.\n\n"
            "## Section 1\n\n"
            "Detailed content with multiple paragraphs.\n\n"
            "## Section 2\n\n"
            "More detailed content here.\n\n"
            "## Section 3\n\n"
            "Even more content.\n\n"
            "- List item 1\n"
            "- List item 2\n"
            "```bash\n"
            "echo test\n"
            "```\n"
        )
        result = rule_quality_analyzer("Complete Guide", content)
        assert result.score >= 0.7, f"Expected >= 0.7, got {result.score}"

    def test_low_quality_short_content(self) -> None:
        """Very short content should score < 0.5."""
        result = rule_quality_analyzer("Untitled", "Short.")
        assert result.score < 0.5
        assert len(result.issues) > 0

    def test_missing_title_penalty(self) -> None:
        """Missing or untitled document should get a penalty."""
        result = rule_quality_analyzer(
            "Untitled",
            "# Section 1\n\nThis is some test content that exceeds fifty characters for proper quality analysis.",
        )
        score_with_penalty = result.score

        result_good = rule_quality_analyzer(
            "Good Title",
            "# Section 1\n\nThis is some test content that exceeds fifty characters for proper quality analysis.",
        )
        assert score_with_penalty < result_good.score

    def test_no_headings_issue(self) -> None:
        """Content without markdown headings should report issue."""
        result = rule_quality_analyzer("Plain", "Just plain text without any headings.")
        assert any("headings" in issue.lower() for issue in result.issues)

    def test_todo_marker_issue(self) -> None:
        """Content with TODO markers should flag validity issue."""
        result = rule_quality_analyzer("Draft", "# Draft\n\nTODO: add more details.")
        assert any("TODO" in issue or "placeholder" in issue.lower() for issue in result.issues)

    def test_empty_content(self) -> None:
        """Empty content should score 0."""
        result = rule_quality_analyzer("Empty", "")
        assert result.score < 0.1, f"Expected score < 0.1, got {result.score}"
        assert len(result.issues) > 0

    def test_dimension_scores(self) -> None:
        """Result should include dimension scores."""
        result = rule_quality_analyzer("Test", "# Heading\n\nContent here.")
        assert "completeness" in result.dimension_scores
        assert "structure" in result.dimension_scores
        assert "validity" in result.dimension_scores
        assert all(0.0 <= v <= 1.0 for v in result.dimension_scores.values())


class TestLLMQualityAnalyzer:
    """Tests for second-layer LLM-based quality analyzer."""

    @pytest.mark.asyncio
    async def test_analyze_with_llm(self) -> None:
        """LLMQualityAnalyzer should use structured_output and return QualityResult."""
        mock_llm = AsyncMock()
        mock_llm.structured_output.return_value = {
            "score": 0.85,
            "structural_integrity": 0.9,
            "technical_accuracy": 0.8,
            "executability": 0.85,
            "timeliness": 0.7,
            "issues": ["Missing rollback steps"],
            "suggestions": ["Add monitoring metrics"],
        }

        analyzer = LLMQualityAnalyzer(llm_client=mock_llm)
        result = await analyzer.analyze("Test Doc", "# Content")

        assert result.score == 0.85
        assert "Missing rollback steps" in result.issues
        assert "Add monitoring metrics" in result.suggestions
        assert result.dimension_scores["structural_integrity"] == 0.9
        assert result.dimension_scores["technical_accuracy"] == 0.8
        mock_llm.structured_output.assert_called_once()

    @pytest.mark.asyncio
    async def test_analyze_llm_error(self) -> None:
        """When LLM fails, should return fallback result with error info."""
        mock_llm = AsyncMock()
        mock_llm.structured_output.side_effect = ValueError("LLM error")

        analyzer = LLMQualityAnalyzer(llm_client=mock_llm)
        result = await analyzer.analyze("Title", "Content")

        assert result.score == 0.0
        assert any("LLM quality analysis failed" in i for i in result.issues)

    @pytest.mark.asyncio
    async def test_analyze_with_cache(self) -> None:
        """With cache enabled, second call should use cached result."""
        mock_llm = AsyncMock()
        mock_llm.structured_output.return_value = {
            "score": 0.9,
            "structural_integrity": 0.9,
            "technical_accuracy": 0.9,
            "executability": 0.9,
            "timeliness": 0.9,
            "issues": [],
            "suggestions": [],
        }

        from app.llm.cache import clear_cache

        clear_cache()

        analyzer = LLMQualityAnalyzer(llm_client=mock_llm)

        # First call
        result1 = await analyzer.analyze("Title", "Same content")
        assert result1.score == 0.9
        assert mock_llm.structured_output.call_count == 1

        # Second call with same content - should use cache
        mock_llm.structured_output.reset_mock()
        result2 = await analyzer.analyze("Title", "Same content")
        assert result2.score == 0.9
        mock_llm.structured_output.assert_not_called()

    def test_dict_to_quality_result(self) -> None:
        """_dict_to_quality_result should handle partial data."""
        analyzer = LLMQualityAnalyzer(llm_client=AsyncMock())

        result = analyzer._dict_to_quality_result(
            {
                "score": 0.75,
                "issues": ["Issue 1"],
                "suggestions": ["Suggestion 1"],
            }
        )

        assert result.score == 0.75
        assert result.issues == ["Issue 1"]
        assert result.suggestions == ["Suggestion 1"]


class TestAnalyzeDocumentQuality:
    """Tests for the top-level analyze_document_quality function (two-layer)."""

    @pytest.mark.asyncio
    async def test_rule_high_quality_no_llm(self) -> None:
        """When rule score >= 0.8, should not call LLM."""
        doc = KnowledgeDocument(
            id="doc-001",
            title="Comprehensive Guide",
            content=(
                "# Overview\n\n"
                "This is a comprehensive document with detailed content.\n\n"
                "# Prerequisites\n\n"
                "Before proceeding, ensure all prerequisites are met.\n\n"
                "# Procedure\n\n"
                "Step-by-step instructions for completing the task.\n\n"
                "# Configuration\n\n"
                "Detailed configuration parameters and their descriptions.\n\n"
                "# Troubleshooting\n\n"
                "Common issues and their resolutions.\n\n"
                "# Rollback\n\n"
                "Steps to revert changes if needed.\n\n"
                "- List item\n"
                "```\n"
                "code example\n"
                "```\n"
            ),
        )

        mock_llm = AsyncMock()
        result = await analyze_document_quality(doc, use_llm_fallback=True, llm_client=mock_llm)

        assert result.score >= 0.8
        mock_llm.structured_output.assert_not_called()

    @pytest.mark.asyncio
    async def test_rule_low_quality_calls_llm(self) -> None:
        """When rule score < 0.8, should fall back to LLM."""
        doc = KnowledgeDocument(
            id="doc-002",
            title="Quick Note",
            content="Brief note with no structure.",
        )

        mock_llm = AsyncMock()
        mock_llm.structured_output.return_value = {
            "score": 0.6,
            "structural_integrity": 0.5,
            "technical_accuracy": 0.6,
            "executability": 0.5,
            "timeliness": 0.7,
            "issues": ["No clear structure"],
            "suggestions": ["Add headings and organize content"],
        }

        result = await analyze_document_quality(doc, use_llm_fallback=True, llm_client=mock_llm)

        assert result.score >= 0.5
        mock_llm.structured_output.assert_called_once()

    @pytest.mark.asyncio
    async def test_llm_fallback_disabled(self) -> None:
        """When use_llm_fallback=False, should never call LLM."""
        doc = KnowledgeDocument(
            id="doc-003",
            title="Brief",
            content="Short content.",
        )

        mock_llm = AsyncMock()
        result = await analyze_document_quality(doc, use_llm_fallback=False, llm_client=mock_llm)

        assert result.score < 0.5  # Rule-based low quality
        mock_llm.structured_output.assert_not_called()


class TestQualityResult:
    """Tests for QualityResult dataclass."""

    def test_default_creation(self) -> None:
        """Should create with default values."""
        qr = QualityResult()
        assert qr.score == 0.0
        assert qr.issues == []
        assert qr.suggestions == []
        assert qr.dimension_scores == {}

    def test_full_creation(self) -> None:
        """Should create with all fields."""
        qr = QualityResult(
            score=0.85,
            issues=["Missing rollback"],
            suggestions=["Add rollback section"],
            dimension_scores={"structural": 0.9, "accuracy": 0.8},
        )
        assert qr.score == 0.85
        assert len(qr.issues) == 1
        assert len(qr.suggestions) == 1
        assert qr.dimension_scores["structural"] == 0.9

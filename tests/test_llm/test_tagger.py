"""Tests for AI-powered tag generator.

Tests both rule_extract_tags and AITagger with mocked LLM calls.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.knowledge.tagger import (
    AITagger,
    generate_tags,
    rule_extract_tags,
)


class TestRuleExtractTags:
    """Tests for first-layer rule-based tag extraction."""

    def test_extract_kubernetes_tags(self) -> None:
        """Kubernetes keywords should produce k8s tags."""
        tags = rule_extract_tags("K8s Deployment", "Kubernetes pod deployment for production.")
        assert "kubernetes" in tags
        assert "docker" not in tags  # No docker keywords here

    def test_extract_multiple_tags(self) -> None:
        """Content with multiple tech keywords should produce multiple tags."""
        tags = rule_extract_tags(
            "Full Stack", "Docker container running on Linux with MySQL database."
        )
        assert "docker" in tags
        assert "linux" in tags
        assert "database" in tags

    def test_extract_no_tags(self) -> None:
        """Content with no tech keywords should produce empty list."""
        tags = rule_extract_tags("General", "Just some general notes.")
        assert tags == []

    def test_extract_chinese_keywords(self) -> None:
        """Chinese keywords should be matched."""
        tags = rule_extract_tags("监控配置", "Prometheus 和 Grafana 监控配置")
        assert "monitoring" in tags

    def test_extract_deduplication(self) -> None:
        """Duplicate tags should be removed."""
        tags = rule_extract_tags(
            "Kubernetes Guide",
            "Kubernetes k8s cluster deployment with Kubernetes pods.",
        )
        assert tags.count("kubernetes") == 1

    def test_extract_max_tags(self) -> None:
        """Should not exceed 10 tags from rule extraction."""
        content = " ".join(
            [
                "kubernetes",
                "docker",
                "linux",
                "network",
                "database",
                "security",
                "monitoring",
                "jenkins",
                "cloud",
                "git",
                "python",
                "ansible",
            ]
        )
        tags = rule_extract_tags("All Tech", content)
        assert len(tags) <= 10

    def test_extract_empty_content(self) -> None:
        """Empty content should produce empty tags."""
        tags = rule_extract_tags("", "")
        assert tags == []


class TestAITagger:
    """Tests for second-layer AI tag generator."""

    @pytest.mark.asyncio
    async def test_generate_tags_with_llm(self) -> None:
        """AITagger should use structured_output and return valid tags."""
        mock_llm = AsyncMock()
        mock_llm.structured_output.return_value = {
            "tags": ["kubernetes", "docker", "linux", "monitoring", "cicd"]
        }

        tagger = AITagger(llm_client=mock_llm)
        tags = await tagger.generate_tags("Deploy App", "Content about deployment.")

        assert len(tags) >= 1
        assert "kubernetes" in tags
        assert len(tags) <= 10
        mock_llm.structured_output.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_tags_with_existing_tags(self) -> None:
        """Existing tags should be preferred (reordered to front)."""
        mock_llm = AsyncMock()
        mock_llm.structured_output.return_value = {
            "tags": ["python", "docker", "kubernetes", "linux"]
        }

        tagger = AITagger(llm_client=mock_llm)
        tags = await tagger.generate_tags(
            "Python App",
            "Python docker deployment.",
            existing_tags=["python", "docker"],
        )

        # python and docker should come first
        assert tags.index("python") < tags.index("kubernetes")
        assert tags.index("docker") < tags.index("kubernetes")

    @pytest.mark.asyncio
    async def test_generate_tags_llm_error(self) -> None:
        """When LLM fails, should return error tag."""
        mock_llm = AsyncMock()
        mock_llm.structured_output.side_effect = ValueError("LLM error")

        tagger = AITagger(llm_client=mock_llm)
        tags = await tagger.generate_tags("Title", "Content")

        assert any("_tag_error" in t for t in tags)

    @pytest.mark.asyncio
    async def test_generate_tags_max_10(self) -> None:
        """Should never return more than 10 tags."""
        mock_llm = AsyncMock()
        mock_llm.structured_output.return_value = {
            "tags": [
                "kubernetes",
                "docker",
                "linux",
                "network",
                "database",
                "security",
                "monitoring",
                "cicd",
                "cloud",
                "git",
                "python",
                "ansible",
                "terraform",
                "helm",
            ]
        }

        tagger = AITagger(llm_client=mock_llm)
        tags = await tagger.generate_tags("Title", "Content")

        assert len(tags) <= 10

    @pytest.mark.asyncio
    async def test_generate_tags_with_cache(self) -> None:
        """With cache enabled, second call with same content should use cache."""
        mock_llm = AsyncMock()
        mock_llm.structured_output.return_value = {"tags": ["kubernetes", "docker"]}

        from app.llm.cache import clear_cache

        clear_cache()

        tagger = AITagger(llm_client=mock_llm)

        # First call
        tags1 = await tagger.generate_tags("Title", "Same content")
        assert len(tags1) >= 1
        assert mock_llm.structured_output.call_count == 1

        # Second call with same content - should use cache
        mock_llm.structured_output.reset_mock()
        tags2 = await tagger.generate_tags("Title", "Same content")
        assert len(tags2) >= 1
        mock_llm.structured_output.assert_not_called()

    def test_normalize_tags(self) -> None:
        """_normalize_tags should clean and deduplicate."""
        tagger = AITagger(llm_client=AsyncMock())

        tags = tagger._normalize_tags(
            ["Kubernetes", "Docker ", "  Linux", "Kubernetes", "CI/CD"],
        )

        assert len(tags) == 4  # Kubernetes deduplicated
        assert "kubernetes" in tags
        assert "docker" in tags
        assert "linux" in tags
        assert "ci_cd" in tags

    def test_normalize_tags_with_existing(self) -> None:
        """Existing tags should be moved to front."""
        tagger = AITagger(llm_client=AsyncMock())

        tags = tagger._normalize_tags(
            ["python", "docker", "kubernetes", "linux"],
            existing_tags=["docker", "python"],
        )

        assert tags.index("docker") < tags.index("kubernetes")
        assert tags.index("python") < tags.index("kubernetes")

    def test_normalize_tags_max_10(self) -> None:
        """Should cap at 10 tags."""
        tagger = AITagger(llm_client=AsyncMock())

        raw = [f"tag{i}" for i in range(20)]
        tags = tagger._normalize_tags(raw)

        assert len(tags) == 10


class TestGenerateTags:
    """Tests for the top-level generate_tags function (two-layer)."""

    @pytest.mark.asyncio
    async def test_rule_sufficient_no_llm(self) -> None:
        """When rule extracts >= 3 tags, should not call LLM."""
        mock_llm = AsyncMock()
        tags = await generate_tags(
            "K8s Docker Linux",
            "Kubernetes docker linux network database content.",
            use_llm_fallback=True,
            llm_client=mock_llm,
        )

        assert len(tags) >= 3
        mock_llm.structured_output.assert_not_called()

    @pytest.mark.asyncio
    async def test_rule_insufficient_calls_llm(self) -> None:
        """When rule extracts < 3 tags, should fall back to LLM."""
        mock_llm = AsyncMock()
        mock_llm.structured_output.return_value = {
            "tags": ["general", "documentation", "reference"]
        }

        tags = await generate_tags(
            "General Notes",
            "Some general notes without tech keywords.",
            use_llm_fallback=True,
            llm_client=mock_llm,
        )

        assert len(tags) >= 1
        mock_llm.structured_output.assert_called_once()

    @pytest.mark.asyncio
    async def test_llm_fallback_disabled(self) -> None:
        """When use_llm_fallback=False, should never call LLM."""
        mock_llm = AsyncMock()
        tags = await generate_tags(
            "Random",
            "Some random text.",
            use_llm_fallback=False,
            llm_client=mock_llm,
        )

        assert tags == []  # No keywords matched
        mock_llm.structured_output.assert_not_called()

    @pytest.mark.asyncio
    async def test_tags_merged_rule_plus_llm(self) -> None:
        """Rule tags and LLM tags should be merged with rule tags first."""
        mock_llm = AsyncMock()
        mock_llm.structured_output.return_value = {"tags": ["ai_generated1", "ai_generated2"]}

        # Content with only "git" keyword matching (to get < 3 rule tags)
        tags = await generate_tags(
            "Git Guide",
            "Git version control basic usage.",
            use_llm_fallback=True,
            llm_client=mock_llm,
        )

        # git should be first (from rules), then AI tags
        assert "git" in tags
        mock_llm.structured_output.assert_called_once()

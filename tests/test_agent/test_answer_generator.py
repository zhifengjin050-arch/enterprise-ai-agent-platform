"""Tests for answer generator.

Tests LLM-based answer generation with structured_output,
including caching and LLM failure fallback.
"""
from __future__ import annotations

from typing import Any, Dict
from unittest.mock import AsyncMock

import pytest

from app.agent.answer_generator import AnswerGenerator, AnswerResult, generate_answer
from app.prompts.answer_generation import (
    ANSWER_SCHEMA,
    ANSWER_SYSTEM_PROMPT,
    build_answer_prompt,
)


class TestAnswerResult:
    """Tests for AnswerResult dataclass."""

    def test_answer_result_fields(self) -> None:
        """AnswerResult should store all fields."""
        result = AnswerResult(
            answer="Nginx 502通常由于upstream不可用导致",
            confidence=0.85,
            reasoning_summary="Found matching context in SOP documents",
            used_sources=["Nginx故障处理SOP"],
        )
        assert result.answer == "Nginx 502通常由于upstream不可用导致"
        assert result.confidence == 0.85
        assert result.reasoning_summary == "Found matching context in SOP documents"
        assert result.used_sources == ["Nginx故障处理SOP"]


class TestBuildAnswerPrompt:
    """Tests for build_answer_prompt."""

    def test_build_prompt_with_context(self) -> None:
        """Prompt should include query and context."""
        prompt = build_answer_prompt(
            query="nginx 502怎么排查",
            context_text="[文档 1]\n标题: Nginx故障处理SOP\n内容: 502排查步骤",
        )
        assert "nginx 502怎么排查" in prompt
        assert "Nginx故障处理SOP" in prompt
        assert "502排查步骤" in prompt

    def test_build_prompt_with_history(self) -> None:
        """Prompt should include history when provided."""
        prompt = build_answer_prompt(
            query="怎么解决",
            context_text="[文档 1]\n标题: SOP\n内容: 步骤",
            history_text="用户: 之前nginx 502了\n助手: 建议排查upstream",
        )
        assert "用户: 之前nginx 502了" in prompt
        assert "助手: 建议排查upstream" in prompt

    def test_build_prompt_empty_context(self) -> None:
        """Prompt should handle empty context."""
        prompt = build_answer_prompt(
            query="test",
            context_text="",
        )
        assert "test" in prompt


class TestAnswerGenerator:
    """Tests for AnswerGenerator."""

    @pytest.mark.asyncio
    async def test_generate_success(self) -> None:
        """Successful LLM call should return structured answer."""
        mock_llm = AsyncMock()
        async def mock_structured_output(prompt: str, schema: Dict[str, Any], **kwargs):
            return {
                "answer": "Nginx 502通常由于upstream不可用导致",
                "confidence": 0.85,
                "reasoning_summary": "Matched SOP content",
                "used_sources": ["Nginx故障处理SOP"],
            }
        mock_llm.structured_output = mock_structured_output

        generator = AnswerGenerator(llm_client=mock_llm)
        result = await generator.generate(
            query="nginx 502怎么排查",
            context_text="[文档 1]\n标题: Nginx故障处理SOP\n内容: 502排查步骤",
        )
        assert "Nginx 502" in result.answer
        assert result.confidence == 0.85
        assert result.used_sources == ["Nginx故障处理SOP"]

    @pytest.mark.asyncio
    async def test_generate_llm_failure_fallback(self) -> None:
        """LLM failure should return fallback answer."""
        mock_llm = AsyncMock()
        async def mock_fail(*args, **kwargs):
            raise ConnectionError("API unreachable")
        mock_llm.structured_output = mock_fail

        generator = AnswerGenerator(llm_client=mock_llm)
        result = await generator.generate(
            query="test",
            context_text="context",
        )
        assert "暂时不可用" in result.answer
        assert result.confidence == 0.0

    @pytest.mark.asyncio
    async def test_generate_with_cache(self) -> None:
        """Cached results should be returned without LLM call."""
        mock_llm = AsyncMock()
        call_count = 0
        async def mock_structured_output(prompt: str, schema: Dict[str, Any], **kwargs):
            nonlocal call_count
            call_count += 1
            return {
                "answer": "Cached answer",
                "confidence": 0.9,
                "reasoning_summary": "",
                "used_sources": ["doc1"],
            }
        mock_llm.structured_output = mock_structured_output

        generator = AnswerGenerator(llm_client=mock_llm)
        # Populate cache
        await generator.generate(
            query="test query",
            context_text="context",
        )
        first_calls = call_count

        # Should hit cache now
        result = await generator.generate(
            query="test query",
            context_text="context",
        )
        assert result.answer == "Cached answer"
        assert call_count == first_calls  # Cache hit, no extra call

    @pytest.mark.asyncio
    async def test_generate_empty_context(self) -> None:
        """Empty context should still produce fallback."""
        mock_llm = AsyncMock()
        async def mock_structured_output(prompt: str, schema: Dict[str, Any], **kwargs):
            return {
                "answer": "No relevant documents found",
                "confidence": 0.1,
                "reasoning_summary": "Empty context",
                "used_sources": [],
            }
        mock_llm.structured_output = mock_structured_output

        generator = AnswerGenerator(llm_client=mock_llm)
        result = await generator.generate(
            query="test",
            context_text="",
        )
        assert result.confidence == 0.1


class TestGenerateAnswer:
    """Tests for generate_answer convenience function."""

    @pytest.mark.asyncio
    async def test_generate_answer_basic(self) -> None:
        """generate_answer should return AnswerResult."""
        mock_llm = AsyncMock()
        async def mock_structured_output(*args, **kwargs):
            return {
                "answer": "测试答案",
                "confidence": 0.8,
                "reasoning_summary": "test",
                "used_sources": ["doc1"],
            }
        mock_llm.structured_output = mock_structured_output

        result = await generate_answer(
            query="test",
            context_text="context",
            llm_client=mock_llm,
        )
        assert isinstance(result, AnswerResult)
        assert result.answer == "测试答案"
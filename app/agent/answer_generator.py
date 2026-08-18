"""LLM-based answer generator for knowledge Q&A.

Calls the LLM with structured_output to produce a JSON-formatted
answer with confidence assessment and source attribution.
Uses the global llm_client with api_key fallback behaviour.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from app.llm.cache import cached_call, store_cached_result
from app.prompts.answer_generation import (
    ANSWER_SCHEMA,
    ANSWER_SYSTEM_PROMPT,
    build_answer_prompt,
)


@dataclass
class AnswerResult:
    """Structured answer from LLM.

    Attributes:
        answer: The final answer text for the user.
        confidence: Confidence score (0.0 to 1.0).
        reasoning_summary: Brief internal reasoning summary.
        used_sources: List of source document titles actually used.
    """

    answer: str = ""
    confidence: float = 0.0
    reasoning_summary: str = ""
    used_sources: List[str] = field(default_factory=list)


class AnswerGenerator:
    """Generates structured answers using LLM.

    Args:
        llm_client: Optional LLM client override for testing.
    """

    def __init__(self, llm_client=None):
        if llm_client is not None:
            self._llm = llm_client
        else:
            from app.llm.client import llm_client as _llm

            self._llm = _llm

    async def generate(
        self,
        query: str,
        context_text: str,
        history_text: str = "",
        use_cache: bool = True,
    ) -> AnswerResult:
        """Generate an answer from context.

        Args:
            query: User's question.
            context_text: Formatted context from retrieved documents.
            history_text: Optional conversation history text.
            use_cache: Whether to check cache first.

        Returns:
            AnswerResult with answer, confidence, sources.
        """
        # Build prompt
        prompt = build_answer_prompt(query, context_text, history_text)

        # Check cache
        if use_cache:
            cached_value, hit = cached_call(
                prompt=prompt,
                system_prompt=ANSWER_SYSTEM_PROMPT,
            )
            if hit and isinstance(cached_value, dict):
                return AnswerResult(
                    answer=cached_value.get("answer", ""),
                    confidence=cached_value.get("confidence", 0.0),
                    reasoning_summary=cached_value.get("reasoning_summary", ""),
                    used_sources=cached_value.get("used_sources", []),
                )

        try:
            result = await self._llm.structured_output(
                prompt=prompt,
                schema=ANSWER_SCHEMA,
                system_prompt=ANSWER_SYSTEM_PROMPT,
                temperature=0.3,
                max_tokens=4096,
            )

            answer = AnswerResult(
                answer=result.get("answer", ""),
                confidence=min(1.0, max(0.0, float(result.get("confidence", 0.0)))),
                reasoning_summary=result.get("reasoning_summary", ""),
                used_sources=result.get("used_sources", []),
            )

            # Cache result
            if use_cache:
                store_cached_result(
                    prompt=prompt,
                    result={
                        "answer": answer.answer,
                        "confidence": answer.confidence,
                        "reasoning_summary": answer.reasoning_summary,
                        "used_sources": answer.used_sources,
                    },
                    system_prompt=ANSWER_SYSTEM_PROMPT,
                )

            return answer

        except (ValueError, ConnectionError) as e:
            # LLM failure fallback
            return AnswerResult(
                answer=f"抱歉，AI 回答生成暂时不可用：{e}。请稍后再试。",
                confidence=0.0,
                reasoning_summary=f"LLM call failed: {e}",
                used_sources=[],
            )


async def generate_answer(
    query: str,
    context_text: str,
    history_text: str = "",
    llm_client=None,
) -> AnswerResult:
    """Convenience function for answer generation.

    Args:
        query: User's question.
        context_text: Formatted LLM context.
        history_text: Optional conversation history.
        llm_client: Optional LLM client override.

    Returns:
        AnswerResult with generated answer.
    """
    generator = AnswerGenerator(llm_client=llm_client)
    return await generator.generate(query, context_text, history_text)

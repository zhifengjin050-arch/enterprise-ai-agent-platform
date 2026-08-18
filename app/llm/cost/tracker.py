"""LLM Cost Tracker.

Intercepts LLM calls to record token usage and estimated cost.
Provides a context manager interface for tracking.
"""
from __future__ import annotations

from typing import Dict, Optional

from app.llm.cost.repository import CostRepository

# Simple pricing per 1K tokens (USD) — adjust for your provider
_MODEL_PRICING: Dict[str, Dict[str, float]] = {
    "deepseek-chat": {"input": 0.00014, "output": 0.00028},
    "deepseek-coder": {"input": 0.00014, "output": 0.00028},
    "gpt-4": {"input": 0.03, "output": 0.06},
    "gpt-4-turbo": {"input": 0.01, "output": 0.03},
    "gpt-3.5-turbo": {"input": 0.0015, "output": 0.002},
    "text-embedding-ada-002": {"input": 0.0001, "output": 0.0},
    "default": {"input": 0.001, "output": 0.002},
}


def _estimate_cost(
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
) -> float:
    """Estimate USD cost for an LLM call.

    Args:
        model: Model name.
        prompt_tokens: Input token count.
        completion_tokens: Output token count.

    Returns:
        Estimated cost in USD.
    """
    pricing = _MODEL_PRICING.get(
        model, _MODEL_PRICING["default"]
    )
    input_cost = (prompt_tokens / 1000) * pricing["input"]
    output_cost = (completion_tokens / 1000) * pricing["output"]
    return input_cost + output_cost


class CostTracker:
    """Tracks LLM API call costs.

    Args:
        repository: Optional CostRepository override.
    """

    def __init__(self, repository: Optional[CostRepository] = None):
        self._repo = repository

    async def record_call(
        self,
        session,
        *,
        provider: str = "deepseek",
        model: str = "deepseek-chat",
        request_type: str = "other",
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
    ) -> None:
        """Record a single LLM API call.

        Args:
            session: AsyncSession for persistence.
            provider: LLM provider name.
            model: Model identifier.
            request_type: Request category.
            prompt_tokens: Input token count.
            completion_tokens: Output token count.
        """
        total_tokens = prompt_tokens + completion_tokens
        cost = _estimate_cost(model, prompt_tokens, completion_tokens)

        repo = self._repo or CostRepository(session)
        await repo.create_record(
            provider=provider,
            model=model,
            request_type=request_type,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            estimated_cost=cost,
        )

    @staticmethod
    def estimate_tokens(text: str) -> int:
        """Roughly estimate token count for a text string.

        Averages ~1.3 tokens per word for English/Chinese mixed text.

        Args:
            text: Input text.

        Returns:
            Estimated token count.
        """
        # Rough approximation: ~4 chars per token for English, ~2 for Chinese
        # Using 3 chars per token as a reasonable average
        return max(1, len(text) // 3)

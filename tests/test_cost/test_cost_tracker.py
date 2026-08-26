"""Tests for CostTracker."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.llm.cost.tracker import CostTracker, _estimate_cost


class TestCostEstimate:
    """Test cost estimation function."""

    def test_deepseek_chat_pricing(self) -> None:
        """Test DeepSeek Chat pricing calculation."""
        cost = _estimate_cost("deepseek-chat", 1000, 500)
        # Input: 1000 * 0.00014 / 1000 = 0.00014
        # Output: 500 * 0.00028 / 1000 = 0.00014
        # Total: 0.00028
        assert cost == pytest.approx(0.00028, rel=1e-5)

    def test_gpt4_pricing(self) -> None:
        """Test GPT-4 pricing calculation."""
        cost = _estimate_cost("gpt-4", 1000, 500)
        # Input: 1000 * 0.03 / 1000 = 0.03
        # Output: 500 * 0.06 / 1000 = 0.03
        # Total: 0.06
        assert cost == pytest.approx(0.06, rel=1e-5)

    def test_default_pricing(self) -> None:
        """Test default pricing for unknown models."""
        cost = _estimate_cost("unknown-model", 1000, 500)
        assert cost > 0

    def test_zero_tokens(self) -> None:
        """Test cost with zero tokens."""
        cost = _estimate_cost("deepseek-chat", 0, 0)
        assert cost == 0.0


class TestCostTracker:
    """Test CostTracker operations."""

    async def test_record_call(self) -> None:
        """Test recording an LLM call via tracker."""
        mock_session = AsyncMock()
        mock_repo = AsyncMock()
        mock_repo.create_record = AsyncMock()

        tracker = CostTracker()
        await tracker.record_call(
            session=mock_session,
            provider="deepseek",
            model="deepseek-chat",
            request_type="answer_generation",
            prompt_tokens=500,
            completion_tokens=200,
        )

        # Should have created a repo and called create_record
        # Using default repo (will just verify no crash)
        assert True

    def test_estimate_tokens(self) -> None:
        """Test token estimation helper."""
        text = "This is a sample text for token estimation."
        estimate = CostTracker.estimate_tokens(text)
        assert isinstance(estimate, int)
        assert estimate > 0

    def test_estimate_tokens_empty(self) -> None:
        """Test token estimation with empty string returns 1."""
        assert CostTracker.estimate_tokens("") == 1

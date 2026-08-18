"""Tests for CostRepository."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.llm.cost.models import LLMCostRecord
from app.llm.cost.repository import CostRepository


@pytest.fixture
def mock_session() -> AsyncMock:
    """Create a mock AsyncSession."""
    session = AsyncMock()
    session.execute = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    return session


class TestCostRepository:
    """Test CostRepository operations."""

    async def test_create_record(self, mock_session: AsyncMock) -> None:
        """Test creating a cost record."""
        repo = CostRepository(mock_session)
        record = await repo.create_record(
            provider="openai",
            model="gpt-4",
            request_type="classification",
            prompt_tokens=200,
            completion_tokens=100,
            total_tokens=300,
            estimated_cost=0.006,
        )
        mock_session.add.assert_called_once()
        mock_session.flush.assert_awaited_once()
        assert record.provider == "openai"
        assert record.estimated_cost == 0.006

    async def test_get_today_stats(self, mock_session: AsyncMock) -> None:
        """Test getting today's stats."""
        # Mock records
        record1 = MagicMock(spec=LLMCostRecord)
        record1.total_tokens = 100
        record1.estimated_cost = 0.001

        record2 = MagicMock(spec=LLMCostRecord)
        record2.total_tokens = 200
        record2.estimated_cost = 0.002

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [record1, record2]
        mock_session.execute.return_value = mock_result

        repo = CostRepository(mock_session)
        stats = await repo.get_today_stats()

        assert stats["total_tokens"] == 300
        assert stats["total_cost"] == 0.003
        assert stats["request_count"] == 2

    async def test_get_month_stats(self, mock_session: AsyncMock) -> None:
        """Test getting monthly stats."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        repo = CostRepository(mock_session)
        stats = await repo.get_month_stats()

        assert stats["total_tokens"] == 0
        assert stats["total_cost"] == 0.0
        assert stats["request_count"] == 0

    async def test_get_stats_by_model(self, mock_session: AsyncMock) -> None:
        """Test getting stats grouped by model."""
        record1 = MagicMock(spec=LLMCostRecord)
        record1.model = "gpt-4"
        record1.total_tokens = 500
        record1.estimated_cost = 0.015

        record2 = MagicMock(spec=LLMCostRecord)
        record2.model = "deepseek-chat"
        record2.total_tokens = 300
        record2.estimated_cost = 0.00042

        record3 = MagicMock(spec=LLMCostRecord)
        record3.model = "gpt-4"
        record3.total_tokens = 200
        record3.estimated_cost = 0.006

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [record1, record2, record3]
        mock_session.execute.return_value = mock_result

        repo = CostRepository(mock_session)
        stats = await repo.get_stats_by_model()

        assert len(stats) == 2  # Two distinct models
        gpt4 = next(s for s in stats if s["model"] == "gpt-4")
        assert gpt4["total_tokens"] == 700
        assert gpt4["request_count"] == 2
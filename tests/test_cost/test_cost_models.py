"""Tests for LLM cost tracking models."""

from __future__ import annotations

from app.llm.cost.models import LLMCostRecord, RequestType


class TestRequestType:
    """Test RequestType enum."""

    def test_enum_values(self) -> None:
        """Test all expected request types exist."""
        assert RequestType.CLASSIFICATION.value == "classification"
        assert RequestType.TAGGING.value == "tagging"
        assert RequestType.QUALITY.value == "quality"
        assert RequestType.ANSWER_GENERATION.value == "answer_generation"
        assert RequestType.ENTITY_EXTRACTION.value == "entity_extraction"
        assert RequestType.RELATION_EXTRACTION.value == "relation_extraction"
        assert RequestType.INTENT.value == "intent"
        assert RequestType.QUERY_REWRITE.value == "query_rewrite"
        assert RequestType.OTHER.value == "other"


class TestLLMCostRecord:
    """Test LLMCostRecord model."""

    def test_create_record(self) -> None:
        """Test creating a cost record with explicit fields."""
        record = LLMCostRecord(
            provider="deepseek",
            model="deepseek-chat",
            request_type="answer_generation",
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            estimated_cost=0.00042,
        )
        assert record.provider == "deepseek"
        assert record.model == "deepseek-chat"
        assert record.request_type == "answer_generation"
        assert record.prompt_tokens == 100
        assert record.completion_tokens == 50
        assert record.total_tokens == 150
        assert record.estimated_cost == 0.00042

    def test_record_repr(self) -> None:
        """Test string representation contains key info."""
        import uuid

        record = LLMCostRecord(
            id=str(uuid.uuid4()),
            model="gpt-4",
            request_type="quality",
            total_tokens=500,
            estimated_cost=0.015,
        )
        rep = repr(record)
        assert "gpt-4" in rep
        assert "quality" in rep
        assert "0.015" in rep

    def test_record_partial(self) -> None:
        """Test creating record with only required fields works."""
        record = LLMCostRecord(provider="openai", model="gpt-3.5-turbo")
        assert record.provider == "openai"
        assert record.model == "gpt-3.5-turbo"

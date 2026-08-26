"""Tests for RelationExtractor.

Tests rule-based extraction and LLM fallback for relation extraction.
"""

from __future__ import annotations

from typing import Any, Dict
from unittest.mock import AsyncMock

import pytest

from app.entity.extractor import ExtractedEntity
from app.relation.extractor import ExtractedRelation, RelationExtractor, extract_relations


class TestRelationExtractor:
    """Tests for RelationExtractor."""

    def test_rule_extract_depends_on(self) -> None:
        """Rule should detect "depends on" relations."""
        entities = [
            ExtractedEntity(name="订单服务", entity_type="service"),
            ExtractedEntity(name="Redis", entity_type="technology"),
        ]
        extractor = RelationExtractor()
        results = extractor._rule_extract(
            entities,
            "订单服务 depends on Redis for caching.",
        )
        assert len(results) >= 1
        assert results[0].source == "订单服务"
        assert results[0].target == "Redis"
        assert results[0].relation_type == "depends_on"

    def test_rule_extract_chinese_dependency(self) -> None:
        """Rule should detect Chinese "依赖" relations."""
        entities = [
            ExtractedEntity(name="支付服务", entity_type="service"),
            ExtractedEntity(name="数据库", entity_type="technology"),
        ]
        extractor = RelationExtractor()
        results = extractor._rule_extract(
            entities,
            "支付服务依赖数据库存储交易记录。",
        )
        assert len(results) >= 1
        assert results[0].relation_type == "depends_on"

    def test_rule_extract_empty_entities(self) -> None:
        """No entities should yield no relations."""
        extractor = RelationExtractor()
        results = extractor._rule_extract([], "Some content.")
        assert results == []

    @pytest.mark.asyncio
    async def test_extract_relations_llm_fallback(self) -> None:
        """LLM fallback should add more relations."""
        mock_llm = AsyncMock()

        async def mock_structured_output(prompt: str, schema: Dict[str, Any], **kwargs):
            return {
                "relations": [
                    {
                        "source": "订单服务",
                        "target": "Redis",
                        "type": "depends_on",
                        "confidence": 0.95,
                    },
                ]
            }

        mock_llm.structured_output = mock_structured_output

        entities = [
            ExtractedEntity(name="订单服务", entity_type="service"),
            ExtractedEntity(name="Redis", entity_type="technology"),
        ]
        extractor = RelationExtractor(llm_client=mock_llm)
        results = await extractor.extract_relations(
            entities,
            "订单服务与Redis的关系",
            "订单服务与Redis有依赖关系。",
            use_llm_fallback=True,
        )
        assert len(results) >= 1

    @pytest.mark.asyncio
    async def test_extract_relations_llm_failure(self) -> None:
        """LLM failure should not break extraction."""
        mock_llm = AsyncMock()

        async def mock_fail(*args, **kwargs):
            raise ConnectionError("API unreachable")

        mock_llm.structured_output = mock_fail

        entities = [
            ExtractedEntity(name="服务A", entity_type="service"),
            ExtractedEntity(name="服务B", entity_type="service"),
        ]
        extractor = RelationExtractor(llm_client=mock_llm)
        results = await extractor.extract_relations(
            entities,
            "服务A与B无关",
            "No relation here.",
            use_llm_fallback=True,
        )
        assert isinstance(results, list)


class TestExtractedRelation:
    """Tests for ExtractedRelation dataclass."""

    def test_extracted_relation_fields(self) -> None:
        """ExtractedRelation should store all fields."""
        relation = ExtractedRelation(
            source="订单服务",
            target="Redis",
            relation_type="depends_on",
            confidence=0.92,
        )
        assert relation.source == "订单服务"
        assert relation.target == "Redis"
        assert relation.relation_type == "depends_on"
        assert relation.confidence == 0.92


class TestExtractRelationsFunction:
    """Tests for extract_relations convenience function."""

    @pytest.mark.asyncio
    async def test_extract_relations_function(self) -> None:
        """Convenience function should return ExtractedRelation list."""
        entities = [
            ExtractedEntity(name="服务A", entity_type="service"),
            ExtractedEntity(name="服务B", entity_type="service"),
        ]
        results = await extract_relations(
            entities,
            "标题",
            "服务A depends on 服务B",
            llm_client=None,  # will use default client (no API key = skip LLM)
        )
        assert isinstance(results, list)

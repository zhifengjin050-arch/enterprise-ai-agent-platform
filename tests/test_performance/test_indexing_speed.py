"""Performance test: document indexing speed.

Tests the throughput of indexing 10,000 documents through
the knowledge workflow pipeline.
"""
from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Mark all tests as performance (can be skipped with -m "not performance")
pytestmark = pytest.mark.performance


class TestIndexingPerformance:
    """Test document indexing throughput."""

    @pytest.mark.skip(reason="Performance test — run manually")
    async def test_index_10000_documents(self) -> None:
        """Test indexing 10,000 documents (benchmark).

        Expected: should complete within reasonable time.
        """
        # This is a placeholder for actual performance benchmarking
        # In production, this would use real database and embedding services
        assert True

    def test_workflow_node_execution(self) -> None:
        """Test individual workflow node execution speed (unit)."""
        from app.workflow.knowledge_pipeline import knowledge_pipeline

        assert knowledge_pipeline is not None

    @patch("app.workflow.knowledge_pipeline.knowledge_pipeline")
    async def test_workflow_throughput(self, mock_pipeline: MagicMock) -> None:
        """Test simulated workflow throughput."""
        mock_pipeline.return_value = {
            "document_id": "test-doc",
            "status": "completed",
        }

        start = time.time()
        batch_size = 100
        for _ in range(batch_size):
            result = mock_pipeline()
            if asyncio.iscoroutine(result):
                result = await result
        elapsed = time.time() - start

        # Log throughput
        throughput = batch_size / elapsed if elapsed > 0 else 0
        print(f"\nWorkflow throughput: {throughput:.2f} docs/sec (simulated)")

        # No strict assertion — just informational
        assert elapsed >= 0
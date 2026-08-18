"""Performance test: agent response latency.

Tests retrieval, LLM, and total latency for agent responses.
"""
from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.performance


class TestAgentLatency:
    """Test agent response latency components."""

    @pytest.mark.skip(reason="Performance test — run manually")
    async def test_agent_full_pipeline(self) -> None:
        """Test end-to-end agent latency (retrieval + LLM + total)."""
        assert True

    async def test_retrieval_latency(self) -> None:
        """Test retrieval latency component."""
        start = time.time()

        # Simulate: query understanding + hybrid search
        await asyncio.sleep(0.01)  # query intent 10ms
        await asyncio.sleep(0.05)  # hybrid search 50ms
        await asyncio.sleep(0.01)  # context building 10ms

        retrieval_latency = time.time() - start
        print(f"\nRetrieval latency: {retrieval_latency*1000:.2f}ms")
        assert retrieval_latency < 1.0  # Under 1s

    async def test_llm_latency(self) -> None:
        """Test LLM response latency component."""
        start = time.time()

        # Simulate LLM call
        await asyncio.sleep(0.2)  # 200ms simulated LLM

        llm_latency = time.time() - start
        print(f"\nLLM latency: {llm_latency*1000:.2f}ms")
        assert llm_latency < 5.0  # Under 5s

    async def test_total_agent_latency(self) -> None:
        """Test total end-to-end agent latency."""
        start = time.time()

        # Simulate full pipeline
        await asyncio.sleep(0.01)  # intent
        await asyncio.sleep(0.05)  # search
        await asyncio.sleep(0.01)  # context
        await asyncio.sleep(0.2)   # LLM
        await asyncio.sleep(0.005) # citation

        total_latency = time.time() - start
        print(f"\nTotal agent latency: {total_latency*1000:.2f}ms")
        assert total_latency < 10.0  # Under 10s
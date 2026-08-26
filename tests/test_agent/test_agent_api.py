"""Tests for the Agent API endpoints.

Tests /api/agent/chat and /api/agent/history/{conversation_id}.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.agent.knowledge_agent import KnowledgeAgent, KnowledgeAgentResult
from app.citation.models import CitationSource
from app.main import app


@pytest.fixture
def mock_agent_result() -> KnowledgeAgentResult:
    """Create a mock KnowledgeAgentResult."""
    return KnowledgeAgentResult(
        answer="Nginx 502通常由于upstream不可用导致",
        citations=[
            CitationSource(
                document_id="doc-1",
                title="Nginx故障处理SOP",
                content_snippet="502表示上游服务异常",
                source="knowledge_base",
                score=0.93,
            ),
        ],
        confidence=0.91,
        sources=["Nginx故障处理SOP"],
        conversation_id="conv-123",
        intent="incident_analysis",
    )


class TestAgentChatAPI:
    """Tests for POST /api/agent/chat."""

    @pytest.mark.asyncio
    async def test_chat_success(self, mock_agent_result) -> None:
        """Normal chat should return answer with citations."""
        mock_agent = AsyncMock(spec=KnowledgeAgent)
        mock_agent.ask.return_value = mock_agent_result

        with patch("app.api.agent._get_agent", return_value=mock_agent):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/api/agent/chat",
                    json={"query": "nginx 502怎么排查"},
                )

        assert response.status_code == 200
        data = response.json()
        assert "Nginx 502" in data["answer"]
        assert len(data["citations"]) > 0
        assert data["confidence"] == 0.91
        assert data["conversation_id"] == "conv-123"

    @pytest.mark.asyncio
    async def test_chat_empty_query(self) -> None:
        """Empty query should return 400."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/agent/chat",
                json={"query": ""},
            )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_chat_with_conversation_id(self, mock_agent_result) -> None:
        """Providing conversation_id should be passed to agent."""
        mock_agent = AsyncMock(spec=KnowledgeAgent)
        mock_agent.ask.return_value = mock_agent_result

        with patch("app.api.agent._get_agent", return_value=mock_agent):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/api/agent/chat",
                    json={
                        "query": "test",
                        "conversation_id": "existing-conv",
                    },
                )

        assert response.status_code == 200
        mock_agent.ask.assert_called_with(
            query="test",
            conversation_id="existing-conv",
            user_id="",
        )

    @pytest.mark.asyncio
    async def test_chat_agent_failure(self) -> None:
        """Agent failure should be handled gracefully."""
        mock_agent = AsyncMock(spec=KnowledgeAgent)
        mock_agent.ask.side_effect = Exception("Internal error")

        with patch("app.api.agent._get_agent", return_value=mock_agent):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/api/agent/chat",
                    json={"query": "test query"},
                )
        assert response.status_code == 500


class TestAgentHistoryAPI:
    """Tests for GET /api/agent/history/{conversation_id}."""

    @pytest.mark.asyncio
    async def test_get_history_found(self) -> None:
        """Existing conversation should return history."""
        # Pre-seed conversation memory
        from app.conversation.memory import memory as conv_memory

        conv_memory.create_conversation("test-conv-1", title="测试对话")
        conv_memory.add_message("test-conv-1", "user", "问题1")
        conv_memory.add_message("test-conv-1", "assistant", "回答1")

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/agent/history/test-conv-1")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "test-conv-1"
        assert len(data["messages"]) == 2

    @pytest.mark.asyncio
    async def test_get_history_not_found(self) -> None:
        """Non-existent conversation should return 404."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/agent/history/non-existent-id")

        assert response.status_code == 404

"""API tests for /api/agents."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.agent_runtime.models import AgentRecord, AgentResult
from app.main import app as fastapi_app


class TestAgentAPIAuth:
    @pytest.mark.asyncio
    async def test_list_no_auth(self, api_client: AsyncClient) -> None:
        resp = await api_client.get("/api/agents")
        assert resp.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_create_no_auth(self, api_client: AsyncClient) -> None:
        resp = await api_client.post("/api/agents", json={"name": "A"})
        assert resp.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_execute_no_auth(self, api_client: AsyncClient) -> None:
        resp = await api_client.post(
            "/api/agents/fake/execute", json={"query": "hi"}
        )
        assert resp.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_history_no_auth(self, api_client: AsyncClient) -> None:
        resp = await api_client.get("/api/agents/fake/history")
        assert resp.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_chat_no_auth(self, api_client: AsyncClient) -> None:
        resp = await api_client.post("/api/agents/chat", json={"query": "hi"})
        assert resp.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_routes_registered(self, api_client: AsyncClient) -> None:
        resp = await api_client.get("/openapi.json")
        assert resp.status_code == 200
        paths = resp.json()["paths"]
        assert "/api/agents" in paths
        assert "/api/agents/chat" in paths
        assert "/api/agents/{agent_id}/execute" in paths
        assert "/api/agents/{agent_id}/history" in paths

    @pytest.mark.asyncio
    async def test_legacy_agent_still_registered(self, api_client: AsyncClient) -> None:
        resp = await api_client.get("/openapi.json")
        paths = resp.json()["paths"]
        assert "/api/agent/chat" in paths


class TestAgentAPIHappyPath:
    @pytest.mark.asyncio
    async def test_create_list_execute_history(self, auth_api_client: AsyncClient) -> None:
        # Create
        create = await auth_api_client.post(
            "/api/agents",
            json={"name": "KnowledgeBot", "agent_type": "knowledge"},
        )
        assert create.status_code == 200, create.text
        body = create.json()
        assert body["success"] is True
        agent_id = body["data"]["id"]

        # List
        listed = await auth_api_client.get("/api/agents")
        assert listed.status_code == 200
        assert any(a["id"] == agent_id for a in listed.json()["data"])

        # Execute (mock agent.execute to avoid heavy deps)
        fake_result = AgentResult(
            success=True,
            answer="mocked",
            sources=[],
            tool_calls=[],
            task_id="t",
        )
        with patch(
            "app.api.agents.BaseAgent.execute",
            new=AsyncMock(return_value=fake_result),
        ):
            exe = await auth_api_client.post(
                f"/api/agents/{agent_id}/execute",
                json={"query": "为什么 Kubernetes Pod 一直 OOM？"},
            )
        assert exe.status_code == 200, exe.text
        assert exe.json()["data"]["answer"] == "mocked"

        # History
        hist = await auth_api_client.get(f"/api/agents/{agent_id}/history")
        assert hist.status_code == 200
        assert "tasks" in hist.json()["data"]

    @pytest.mark.asyncio
    async def test_execute_not_found(self, auth_api_client: AsyncClient) -> None:
        resp = await auth_api_client.post(
            "/api/agents/00000000-0000-0000-0000-000000000000/execute",
            json={"query": "hi"},
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_history_not_found(self, auth_api_client: AsyncClient) -> None:
        resp = await auth_api_client.get(
            "/api/agents/00000000-0000-0000-0000-000000000000/history"
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_chat_sse(self, auth_api_client: AsyncClient) -> None:
        async def fake_stream(self, input, session=None):
            yield {"type": "thinking", "content": "…"}
            yield {"type": "tool_call", "name": "knowledge_search"}
            yield {"type": "answer", "content": "SSE答案", "success": True}

        with patch(
            "app.api.agents.BaseAgent.stream",
            new=fake_stream,
        ):
            resp = await auth_api_client.post(
                "/api/agents/chat",
                json={"query": "hello"},
            )
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")
        text = resp.text
        assert "thinking" in text or "answer" in text or "SSE" in text

    @pytest.mark.asyncio
    async def test_create_validation(self, auth_api_client: AsyncClient) -> None:
        resp = await auth_api_client.post("/api/agents", json={"name": ""})
        assert resp.status_code == 422

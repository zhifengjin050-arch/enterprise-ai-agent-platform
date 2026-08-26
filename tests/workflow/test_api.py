"""Tests for Workflow Engine API endpoints — Phase 9."""

from __future__ import annotations

from typing import Any, AsyncGenerator, Dict

import pytest
from httpx import AsyncClient


class TestWorkflowAPI:
    """Tests for /api/workflows endpoints."""

    @pytest.fixture
    async def auth_client(self, auth_api_client: AsyncClient) -> AsyncGenerator[AsyncClient, None]:
        yield auth_api_client

    async def test_create_workflow(
        self, auth_client: AsyncClient, sample_workflow_definition: Dict[str, Any]
    ) -> None:
        resp = await auth_client.post("/api/workflows", json=sample_workflow_definition)
        assert resp.status_code in (200, 201), resp.text
        data = resp.json()
        assert data["name"] == "test_workflow"
        assert "id" in data

    async def test_create_workflow_invalid(self, auth_client: AsyncClient) -> None:
        resp = await auth_client.post("/api/workflows", json={"name": "bad"})
        assert resp.status_code == 422

    async def test_list_workflows(
        self, auth_client: AsyncClient, sample_workflow_definition: Dict[str, Any]
    ) -> None:
        await auth_client.post("/api/workflows", json=sample_workflow_definition)
        resp = await auth_client.get("/api/workflows")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    async def test_get_workflow(
        self, auth_client: AsyncClient, sample_workflow_definition: Dict[str, Any]
    ) -> None:
        created = (await auth_client.post("/api/workflows", json=sample_workflow_definition)).json()
        resp = await auth_client.get(f"/api/workflows/{created['id']}")
        assert resp.status_code == 200
        assert resp.json()["id"] == created["id"]

    async def test_get_workflow_not_found(self, auth_client: AsyncClient) -> None:
        resp = await auth_client.get("/api/workflows/nonexistent")
        assert resp.status_code == 404

    async def test_execute_workflow(
        self, auth_client: AsyncClient, sample_workflow_definition: Dict[str, Any]
    ) -> None:
        created = (await auth_client.post("/api/workflows", json=sample_workflow_definition)).json()
        resp = await auth_client.post(f"/api/workflows/{created['id']}/execute", json={})
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["status"] == "RUNNING"

    async def test_execute_workflow_not_found(self, auth_client: AsyncClient) -> None:
        resp = await auth_client.post("/api/workflows/nonexistent/execute", json={})
        assert resp.status_code == 400

    async def test_list_runs(
        self, auth_client: AsyncClient, sample_workflow_definition: Dict[str, Any]
    ) -> None:
        created = (await auth_client.post("/api/workflows", json=sample_workflow_definition)).json()
        await auth_client.post(f"/api/workflows/{created['id']}/execute", json={})
        resp = await auth_client.get(f"/api/workflows/{created['id']}/runs")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    async def test_get_run(
        self, auth_client: AsyncClient, sample_workflow_definition: Dict[str, Any]
    ) -> None:
        created = (await auth_client.post("/api/workflows", json=sample_workflow_definition)).json()
        run = (await auth_client.post(f"/api/workflows/{created['id']}/execute", json={})).json()
        resp = await auth_client.get(f"/api/workflows/runs/{run['id']}")
        assert resp.status_code == 200
        assert resp.json()["id"] == run["id"]

    async def test_get_run_not_found(self, auth_client: AsyncClient) -> None:
        resp = await auth_client.get("/api/workflows/runs/nonexistent")
        assert resp.status_code == 404

    async def test_cancel_run_by_run_id(
        self, auth_client: AsyncClient, sample_workflow_with_approval: Dict[str, Any]
    ) -> None:
        created = (
            await auth_client.post("/api/workflows", json=sample_workflow_with_approval)
        ).json()
        run = (await auth_client.post(f"/api/workflows/{created['id']}/execute", json={})).json()
        import asyncio

        await asyncio.sleep(0.3)
        resp = await auth_client.post(f"/api/workflows/runs/{run['id']}/cancel")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["status"] == "FAILED"

    async def test_cancel_workflow_by_id(
        self, auth_client: AsyncClient, sample_workflow_with_approval: Dict[str, Any]
    ) -> None:
        created = (
            await auth_client.post("/api/workflows", json=sample_workflow_with_approval)
        ).json()
        await auth_client.post(f"/api/workflows/{created['id']}/execute", json={})
        import asyncio

        await asyncio.sleep(0.3)
        resp = await auth_client.post(f"/api/workflows/{created['id']}/cancel")
        assert resp.status_code == 200, resp.text

    async def test_run_events(
        self, auth_client: AsyncClient, sample_workflow_definition: Dict[str, Any]
    ) -> None:
        created = (await auth_client.post("/api/workflows", json=sample_workflow_definition)).json()
        run = (await auth_client.post(f"/api/workflows/{created['id']}/execute", json={})).json()
        import asyncio

        await asyncio.sleep(0.5)
        resp = await auth_client.get(f"/api/workflows/runs/{run['id']}/events")
        assert resp.status_code == 200
        events = resp.json()
        assert isinstance(events, list)
        assert len(events) >= 2

    async def test_webhook_trigger(
        self, auth_client: AsyncClient, sample_workflow_with_approval: Dict[str, Any]
    ) -> None:
        created = (
            await auth_client.post("/api/workflows", json=sample_workflow_with_approval)
        ).json()
        resp = await auth_client.post(
            f"/api/workflows/webhook/{created['id']}",
            json={"event": "push", "ref": "main"},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["status"] == "RUNNING"

"""Knowledge API integration tests."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_api_knowledge_crud(api_client: AsyncClient) -> None:
    create_resp = await api_client.post(
        "/api/knowledge/documents",
        json={
            "title": "API Doc",
            "content": "API created content about Kubernetes",
            "doc_type": "ARCHITECTURE",
            "tags": ["k8s"],
            "author": "api-tester",
        },
    )
    assert create_resp.status_code == 200
    created = create_resp.json()["document"]
    doc_id = created["id"]
    assert created["title"] == "API Doc"
    assert "k8s" in created["tags"]

    list_resp = await api_client.get("/api/knowledge/documents")
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] >= 1

    get_resp = await api_client.get(f"/api/knowledge/documents/{doc_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == doc_id

    delete_resp = await api_client.delete(f"/api/knowledge/documents/{doc_id}")
    assert delete_resp.status_code == 200
    assert delete_resp.json()["message"] == "Document archived"

    missing = await api_client.get("/api/knowledge/documents/00000000-0000-0000-0000-000000000099")
    assert missing.status_code == 404

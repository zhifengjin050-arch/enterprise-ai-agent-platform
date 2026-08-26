"""API contract tests that keep the console and backend aligned."""

from __future__ import annotations

from app.api.agents import ExecuteAgentRequest
from app.knowledge.retrieval import RetrievalResult


def test_execute_agent_accepts_task_alias() -> None:
    body = ExecuteAgentRequest.model_validate({"task": "生产环境 Pod OOM"})
    assert body.query == "生产环境 Pod OOM"


def test_execute_agent_accepts_query() -> None:
    body = ExecuteAgentRequest.model_validate({"query": "hello"})
    assert body.query == "hello"


def test_retrieval_result_exposes_id_alias() -> None:
    payload = RetrievalResult(
        document_id="doc-1", title="Runbook", content="...", score=0.9
    ).to_dict()
    assert payload["id"] == "doc-1"
    assert payload["document_id"] == "doc-1"

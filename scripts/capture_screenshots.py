#!/usr/bin/env python3
"""Capture README screenshots at 1440x900.

Prefers a running frontend (Docker :80 or Vite :5173/:4173).
Auth-gated APIs are mocked so Agent / Workflow / Monitor pages render content.
Connector / Security images are taken from docs/screenshots/html previews.

Usage:
    pip install playwright
    python -m playwright install chromium
    python scripts/capture_screenshots.py
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "screenshots"
HTML = OUT / "html"
VIEWPORT = {"width": 1440, "height": 900}

MOCK_AGENTS = {
    "success": True,
    "total": 1,
    "data": [
        {
            "id": "agent-demo-1",
            "tenant_id": "cloudtech",
            "name": "Enterprise Assistant",
            "agent_type": "knowledge",
            "enabled": True,
            "config_json": {},
            "created_at": "2026-08-18T10:00:00Z",
        }
    ],
}

MOCK_EXECUTE = {
    "success": True,
    "conversation_id": "conv-1",
    "task_id": "task-1",
    "data": {
        "success": True,
        "answer": "Pod OOM 时先确认 memory limit，再查看 recent events 与 cgroup 指标，必要时滚动扩容。",
        "sources": [
            {
                "id": "doc-k8s",
                "title": "Kubernetes 运维规范",
                "content": "当 Pod 出现 OOM 错误时：检查 Request/Limit...",
                "score": 0.92,
            }
        ],
        "tool_calls": [
            {
                "tool": "knowledge_search",
                "input": {"query": "Pod OOM"},
                "output": {"hits": 3},
            }
        ],
    },
}

MOCK_WORKFLOWS = [
    {
        "id": "wf-incident",
        "name": "Incident Analysis",
        "description": "Analyze incidents with knowledge retrieval and approval",
        "status": "CREATED",
        "node_count": 4,
        "trigger_type": "api",
        "version": "1.0",
    }
]

MOCK_RUNS = [
    {
        "id": "run-1",
        "status": "COMPLETED",
        "started_at": "2026-08-18T10:05:00Z",
        "finished_at": "2026-08-18T10:05:12Z",
    }
]

MOCK_HEALTH = {
    "status": "healthy",
    "version": "1.0.0",
    "service": "backend",
    "app_name": "Enterprise AI Agent Platform",
    "components": {"database": "healthy", "redis": "healthy", "chroma": "healthy"},
}

MOCK_KNOWLEDGE_STATS = {
    "total_documents": 5,
    "total_categories": 5,
    "total_tags": 8,
    "by_type": {"SOP": 2, "CONFIGURATION": 1, "OTHER": 2},
}

MOCK_DOCS = {
    "results": [
        {
            "id": "1",
            "title": "Kubernetes 运维规范",
            "content": "生产集群使用 Kubernetes v1.28+",
            "format": "markdown",
            "doc_type": "SOP",
            "status": "PUBLISHED",
            "source": "local",
            "version": 1,
            "author": "SRE Team",
            "tags": ["kubernetes", "ops"],
            "created_at": "2026-08-18T10:00:00Z",
            "updated_at": "2026-08-18T10:00:00Z",
        }
    ],
    "total": 5,
}

MOCK_SEARCH = {
    "query": "Pod OOM",
    "total": 2,
    "results": [
        {
            "id": "c1",
            "title": "Kubernetes 运维规范",
            "content": "当 Pod 出现 OOM (Out of Memory) 错误时：检查 Request/Limit...",
            "score": 0.91,
            "metadata": {"source": "hybrid"},
        },
        {
            "id": "c2",
            "title": "事件 SOP",
            "content": "P1 故障需在 15 分钟内响应并同步值班群。",
            "score": 0.74,
            "metadata": {"source": "fulltext"},
        },
    ],
}

MOCK_METRICS_OVERVIEW = {
    "status": "ok",
    "database": "healthy",
    "period_hours": 24,
    "llm_calls": 128,
    "agent_executions": 36,
    "errors_24h": 1,
}

MOCK_METRICS_AGENTS = {
    "total_executions": 36,
    "failed": 1,
    "success_rate": 0.97,
    "components": {"planner": 36, "tools": 80},
}

MOCK_METRICS_LLM = {
    "total_calls": 128,
    "total_tokens": 420000,
    "total_cost": 1.28,
    "prompt_tokens": 300000,
    "completion_tokens": 120000,
    "per_model": [{"model": "deepseek-chat", "calls": 128, "tokens": 420000, "cost": 1.28}],
}

MOCK_METRICS_ERRORS = {"total_errors": 1, "per_component": {"llm": 1}}
MOCK_METRICS_SYNC = {"total_syncs": 12, "failed": 0, "success_rate": 1.0}


def _url_ok(url: str) -> bool:
    try:
        urllib.request.urlopen(url, timeout=3)
        return True
    except Exception:
        return False


def find_frontend() -> str | None:
    for url in ("http://127.0.0.1", "http://localhost:4173", "http://localhost:5173"):
        if _url_ok(url):
            return url
    return None


def install_mocks(page) -> None:
    def fulfill(route, payload, status=200) -> None:
        route.fulfill(
            status=status,
            content_type="application/json",
            body=json.dumps(payload),
        )

    page.route("**/api/health", lambda r: fulfill(r, MOCK_HEALTH))
    # Playwright uses last-registered route first; keep /execute more specific.
    page.route("**/api/agents**", lambda r: fulfill(r, MOCK_AGENTS))
    page.route("**/api/agents/*/execute", lambda r: fulfill(r, MOCK_EXECUTE))
    page.route("**/api/workflows**", lambda r: fulfill(r, MOCK_WORKFLOWS))
    page.route("**/api/workflows/*/runs**", lambda r: fulfill(r, MOCK_RUNS))
    page.route("**/api/knowledge/stats**", lambda r: fulfill(r, MOCK_KNOWLEDGE_STATS))
    page.route("**/api/knowledge/documents**", lambda r: fulfill(r, MOCK_DOCS))
    page.route("**/api/knowledge/search**", lambda r: fulfill(r, MOCK_SEARCH))
    page.route("**/api/metrics/overview**", lambda r: fulfill(r, MOCK_METRICS_OVERVIEW))
    page.route("**/api/metrics/agents**", lambda r: fulfill(r, MOCK_METRICS_AGENTS))
    page.route("**/api/metrics/llm**", lambda r: fulfill(r, MOCK_METRICS_LLM))
    page.route("**/api/metrics/errors**", lambda r: fulfill(r, MOCK_METRICS_ERRORS))
    page.route("**/api/metrics/sync**", lambda r: fulfill(r, MOCK_METRICS_SYNC))


def main() -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Install Playwright: pip install playwright && python -m playwright install chromium")
        return 1

    OUT.mkdir(parents=True, exist_ok=True)
    frontend = find_frontend()
    print("Frontend:", frontend or "(none)")

    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(viewport=VIEWPORT, device_scale_factor=2)
        page = context.new_page()

        if frontend:
            install_mocks(page)
            shots = [
                ("/", "01_dashboard.png"),
                ("/knowledge", "03_knowledge_search.png"),
                ("/workflows", "04_workflow.png"),
                ("/monitor", "06_observability.png"),
            ]
            for path, name in shots:
                page.goto(frontend + path, wait_until="networkidle")
                time.sleep(0.8)
                if name.startswith("03"):
                    box = page.locator("input[placeholder*='搜索']")
                    if box.count():
                        box.first.fill("Pod OOM")
                        btn = page.get_by_role("button", name="搜索")
                        if btn.count():
                            btn.first.click()
                            page.wait_for_timeout(600)
                page.screenshot(path=str(OUT / name), full_page=False)
                print("wrote", name)

            page.goto(frontend + "/agents", wait_until="networkidle")
            time.sleep(0.8)
            exec_btn = page.get_by_role("button", name="执行")
            if exec_btn.count():
                exec_btn.first.click()
                page.wait_for_timeout(300)
                ta = page.locator("textarea")
                if ta.count():
                    ta.first.fill("生产环境 Pod 频繁 OOM，应该怎么排查？")
                run_btn = page.get_by_role("button", name="运行")
                if run_btn.count():
                    run_btn.first.click()
                    page.get_by_text("回答").wait_for(timeout=5000)
                    page.wait_for_timeout(400)
            page.screenshot(path=str(OUT / "02_agent_chat.png"), full_page=False)
            print("wrote 02_agent_chat.png")

        page.goto(HTML.joinpath("connector.html").as_uri(), wait_until="load")
        page.screenshot(path=str(OUT / "05_connector.png"), full_page=False)
        print("wrote 05_connector.png")

        page.goto(HTML.joinpath("security.html").as_uri(), wait_until="load")
        page.screenshot(path=str(OUT / "07_security.png"), full_page=False)
        print("wrote 07_security.png")

        browser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())

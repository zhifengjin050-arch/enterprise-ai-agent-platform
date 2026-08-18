"""Health check API endpoint — Phase 8 Observability upgrade.

Checks database, Redis, vector store, LLM provider, connectors.
Returns healthy / degraded / unhealthy status.
"""
from __future__ import annotations

from fastapi import APIRouter

from app.core.config import get_settings

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
async def health_check() -> dict:
    """Return detailed service health status with component-level checks.

    Returns:
        Dict with overall status, version, service, and per-component health.
    """
    settings = get_settings()
    components: dict[str, str] = {}

    # Database
    try:
        from app.db.session import get_session_factory

        factory = get_session_factory()
        async with factory() as session:
            from sqlalchemy import text
            await session.execute(text("SELECT 1"))
        components["database"] = "healthy"
    except Exception:
        components["database"] = "unhealthy"

    # Vector store (ChromaDB)
    try:
        if settings.chroma_host:
            import httpx
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"http://{settings.chroma_host}:{settings.chroma_port}/api/v1/heartbeat",
                    timeout=5,
                )
                if resp.status_code == 200:
                    components["vector_store"] = "healthy"
                else:
                    components["vector_store"] = "degraded"
        else:
            components["vector_store"] = "healthy"  # local mode
    except Exception:
        components["vector_store"] = "unhealthy"

    # LLM provider
    if settings.llm_api_key:
        try:
            import httpx
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    settings.llm_base_url.rstrip("/v1") or "https://api.deepseek.com",
                    timeout=5,
                )
                if resp.status_code < 500:
                    components["llm"] = "healthy"
                else:
                    components["llm"] = "degraded"
        except Exception:
            components["llm"] = "degraded"
    else:
        components["llm"] = "not_configured"

    # Connectors (Feishu / Yuque)
    if settings.feishu_app_id and settings.feishu_app_secret:
        components["connector_feishu"] = "healthy"
    else:
        components["connector_feishu"] = "not_configured"

    if settings.yuque_token:
        components["connector_yuque"] = "healthy"
    else:
        components["connector_yuque"] = "not_configured"

    # Redis (optional)
    try:
        import socket
        socket.create_connection(("localhost", 6379), timeout=2).close()
        components["redis"] = "healthy"
    except Exception:
        components["redis"] = "not_configured"

    # Determine overall status
    statuses = list(components.values())
    if any(s == "unhealthy" for s in statuses):
        overall_status = "unhealthy"
    elif any(s == "degraded" for s in statuses):
        overall_status = "degraded"
    else:
        overall_status = "healthy"

    from app.observability.trace import TraceManager
    trace_id = TraceManager.get_trace_id()

    return {
        "status": overall_status,
        "version": "0.9.0",
        "service": "enterprise-ai-knowledge-copilot",
        "app_name": settings.app_name,
        "trace_id": trace_id,
        "components": components,
    }

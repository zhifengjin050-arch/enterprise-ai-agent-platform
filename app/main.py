"""Enterprise AI Automation Platform - Application Entry Point.

FastAPI application factory with router registration.
v1.0.0 - Enterprise AI Agent Platform Release Candidate.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.admin import router as admin_router
from app.api.agent import router as agent_router
from app.api.agents import router as agents_router
from app.api.auth import router as auth_router
from app.api.connector import router as connector_router
from app.api.context import router as context_router
from app.api.graph import router as graph_router
from app.api.health import router as health_router
from app.api.incident import router as incident_router
from app.api.knowledge import router as knowledge_router
from app.api.metrics import router as metrics_router
from app.api.monitor import router as monitor_router
from app.api.review import router as review_router
from app.api.search import router as search_router
from app.api.security import router as security_router
from app.api.sop import router as sop_router
from app.api.sync import router as sync_router
from app.api.task import router as task_router
from app.api.workflow import router as workflow_router
from app.api.workflows import router as workflows_router
from app.core.config import get_settings
from app.core.exception_handlers import register_exception_handlers
from app.core.logging import configure_logging, get_logger
from app.core.middleware.metrics import MetricsMiddleware
from app.core.middleware.request_id import RequestIDMiddleware
from app.core.middleware.security import SecurityMiddleware
from app.mcp.router import router as mcp_router
from app.tenant.middleware import TenantMiddleware

settings = get_settings()

# Configure structured logging at startup
configure_logging(level=settings.log_level, json_format=settings.log_json_format)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown events."""
    # Initialize OpenTelemetry tracer
    from app.observability.trace import TraceManager

    TraceManager.initialize(service_name=settings.app_name)

    logger.info(
        "Starting %s v%s",
        settings.app_name,
        "1.0.0",
    )
    logger.info("Database: %s", settings.database_url)
    logger.info(
        "LLM: %s (%s)",
        settings.llm_model,
        "configured" if settings.llm_api_key else "not configured",
    )
    logger.info("Embedding: %s", settings.embedding_model)
    logger.info(
        "ChromaDB: %s",
        "configured" if settings.chroma_host else "local",
    )
    logger.info("Connectors: feishu, yuque, gitlab registered")
    logger.info("Security: TenantMiddleware + SecurityMiddleware enabled")
    logger.info("Observability: OpenTelemetry + Prometheus + structured logging")

    # Start ApprovalService background timeout checker
    from app.workflow_engine.approval import approval_service
    await approval_service.start()
    logger.info("Workflow Engine: ApprovalService timeout checker started")

    # Initialize MCP adapters
    if settings.mcp_server_url or settings.enterprise_devops_mcp_url:
        from app.mcp import get_mcp_adapter_registry
        from app.mcp.discovery import discover_and_register_all_mcp_servers

        await discover_and_register_all_mcp_servers()
        logger.info("MCP: Tool adapters registered with Agent Runtime")
    else:
        logger.info("MCP: Not configured (set MCP_SERVER_URL or ENTERPRISE_DEVOPS_MCP_URL)")

    yield

    # Shutdown MCP clients
    if settings.mcp_server_url or settings.enterprise_devops_mcp_url:
        from app.mcp import get_mcp_adapter_registry

        registry = get_mcp_adapter_registry()
        await registry.close_all()
        logger.info("MCP: All clients closed")

    # Stop ApprovalService background timeout checker
    await approval_service.stop()
    logger.info("Workflow Engine: ApprovalService stopped")
    logger.info("Shutting down %s", settings.app_name)


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description=(
        "Enterprise AI Agent Platform v1.0 - Knowledge Intelligence, "
        "AI Agent Runtime, Workflow Automation Engine, Enterprise Security, "
        "Multi-Tenant SaaS, Connector Framework, and Observability. "
        "One-stop enterprise AI automation platform."
    ),
    lifespan=lifespan,
)

# Middleware (order: last added = outermost). Want: Security → Metrics → RequestID → Tenant → app
app.add_middleware(TenantMiddleware)
app.add_middleware(RequestIDMiddleware)
app.add_middleware(MetricsMiddleware)
_origins = [o.strip() for o in (settings.cors_origins or "*").split(",") if o.strip()]
app.add_middleware(
    SecurityMiddleware,
    allowed_origins=_origins or ["*"],
    rate_limit=settings.rate_limit_per_minute,
)

# Register global exception handlers
register_exception_handlers(app)

# Register API routers — no business logic here
app.include_router(health_router)
app.include_router(knowledge_router)
app.include_router(sop_router)
app.include_router(incident_router)
app.include_router(context_router)
app.include_router(search_router)
app.include_router(review_router)
app.include_router(workflow_router)
app.include_router(agent_router)
app.include_router(agents_router)
app.include_router(graph_router)
app.include_router(auth_router)
app.include_router(security_router)
app.include_router(task_router)
app.include_router(admin_router)
app.include_router(monitor_router)
app.include_router(metrics_router)
app.include_router(connector_router)
app.include_router(sync_router)
app.include_router(mcp_router)
app.include_router(workflows_router)

#!/usr/bin/env python3
"""Seed CloudTech demo tenant, user, documents, agent, workflow, connectors.

Does not change application runtime code. Uses existing repositories.

Usage:
    python scripts/demo_seed.py
"""

from __future__ import annotations

import asyncio
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import select

import app.agent_runtime.models  # noqa: F401
import app.api_key.models  # noqa: F401
import app.audit.models  # noqa: F401
import app.auth.models  # noqa: F401
import app.auth.organization  # noqa: F401
import app.connector.models  # noqa: F401
import app.entity.models  # noqa: F401
import app.incident.models  # noqa: F401
import app.knowledge.chunk_models  # noqa: F401
import app.knowledge.models  # noqa: F401
import app.llm.cost.models  # noqa: F401
import app.observability.models  # noqa: F401
import app.prompt.models  # noqa: F401
import app.quota.models  # noqa: F401
import app.relation.models  # noqa: F401
import app.sop.models  # noqa: F401
import app.sync_engine.models  # noqa: F401
import app.task.models  # noqa: F401
import app.workflow.models  # noqa: F401
import app.workflow_engine.models  # noqa: F401
from app.agent_runtime.models import AgentRecord
from app.auth.repository import TenantRepository, UserRepository
from app.auth.service import AuthService
from app.connector.models import ConnectorConfig
from app.db.session import get_session_factory, init_db
from app.workflow_engine.engine import WorkflowEngine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("demo_seed")

INCIDENT_WORKFLOW = {
    "name": "Incident Analysis",
    "description": "Analyze incidents with knowledge retrieval and approval",
    "version": "1.0",
    "trigger_type": "api",
    "tags": ["incident", "demo"],
    "nodes": [
        {"type": "trigger", "name": "start", "next": "analyze"},
        {
            "type": "agent",
            "name": "analyze",
            "config": {"agent_name": "Enterprise Assistant"},
            "next": "review",
        },
        {
            "type": "approval",
            "name": "review",
            "config": {"approvers": ["admin"], "message": "Approve incident analysis?"},
            "next": "finish",
        },
        {"type": "end", "name": "finish"},
    ],
}


async def seed_identity(session) -> str:
    """Create CloudTech tenant and admin user. Returns tenant_id string."""
    tenants = TenantRepository(session)
    users = UserRepository(session)
    auth = AuthService()

    tenant = await tenants.find_by_name("CloudTech")
    if tenant is None:
        tenant = await tenants.create_tenant(
            name="CloudTech",
            description="CloudTech demo enterprise for GitHub showcase",
        )
        logger.info("Created tenant CloudTech id=%s", tenant.id)
    else:
        logger.info("Tenant CloudTech already exists id=%s", tenant.id)

    tenant_id = str(tenant.id)
    existing = await users.find_by_username("admin")
    if existing is None:
        await auth.register_user(
            session,
            username="admin",
            password="admin123",
            email="admin@cloudtech.demo",
            tenant_id=tenant_id,
        )
        logger.info("Created user admin")
    else:
        logger.info("User admin already exists")
    return tenant_id


async def seed_agent(session, tenant_id: str) -> None:
    result = await session.execute(
        select(AgentRecord).where(AgentRecord.name == "Enterprise Assistant")
    )
    if result.scalar_one_or_none() is not None:
        logger.info("Agent Enterprise Assistant already exists")
        return
    session.add(
        AgentRecord(
            name="Enterprise Assistant",
            agent_type="knowledge",
            tenant_id=tenant_id,
            enabled=True,
            config_json={"role": "enterprise_knowledge_copilot"},
        )
    )
    logger.info("Created agent Enterprise Assistant")


async def seed_connectors(session, tenant_id: str) -> None:
    specs = [
        ("CloudTech Feishu", "feishu"),
        ("CloudTech Yuque", "yuque"),
        ("CloudTech GitLab", "gitlab"),
    ]
    for name, ctype in specs:
        result = await session.execute(select(ConnectorConfig).where(ConnectorConfig.name == name))
        if result.scalar_one_or_none() is not None:
            continue
        session.add(
            ConnectorConfig(
                tenant_id=tenant_id,
                name=name,
                type=ctype,
                config_json={"demo": True},
                enabled=True,
                last_sync_at=datetime.now(timezone.utc),
            )
        )
        logger.info("Created connector %s", name)


async def seed_workflow(tenant_id: str) -> None:
    engine = WorkflowEngine()
    existing = await engine.get_workflows(tenant_id=tenant_id, limit=50)
    if any(w.get("name") == "Incident Analysis" for w in existing):
        logger.info("Workflow Incident Analysis already exists")
        return
    created = await engine.create_workflow(
        INCIDENT_WORKFLOW, tenant_id=tenant_id, created_by="admin"
    )
    logger.info("Created workflow %s id=%s", created.get("name"), created.get("id"))


async def seed_documents() -> None:
    from scripts.init_demo_data import main as import_docs

    await import_docs()


async def main() -> None:
    logger.info("Initializing database tables")
    await init_db()

    factory = get_session_factory()
    async with factory() as session:
        tenant_id = await seed_identity(session)
        await seed_agent(session, tenant_id)
        await seed_connectors(session, tenant_id)
        await session.commit()

    await seed_workflow(tenant_id)
    await seed_documents()
    logger.info("Demo seed complete (CloudTech / admin / Enterprise Assistant)")


if __name__ == "__main__":
    asyncio.run(main())

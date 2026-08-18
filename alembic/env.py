"""Alembic environment for async SQLAlchemy migrations."""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.core.config import get_settings
from app.db.base import Base

# Import all models so metadata is complete
import app.auth.models  # noqa: F401
import app.entity.models  # noqa: F401
import app.incident.models  # noqa: F401
import app.knowledge.models  # noqa: F401
import app.llm.cost.models  # noqa: F401
import app.relation.models  # noqa: F401
import app.sop.models  # noqa: F401
import app.task.models  # noqa: F401
import app.connector.models  # noqa: F401
import app.workflow.models  # noqa: F401
import app.sync_engine.models  # noqa: F401
import app.knowledge.chunk_models  # noqa: F401
import app.agent_runtime.models  # noqa: F401
import app.prompt.models  # noqa: F401
import app.auth.organization  # noqa: F401
import app.api_key.models  # noqa: F401
import app.audit.models  # noqa: F401
import app.quota.models  # noqa: F401
import app.observability.models  # noqa: F401
import app.workflow_engine.models  # noqa: F401

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.database_url)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Run migrations given a sync connection wrapper."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in async online mode."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

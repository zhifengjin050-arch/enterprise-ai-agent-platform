"""
Initialize database tables and seed default categories/tags.

Usage:
    python -m scripts.init_db
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Ensure project root is on sys.path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db.session import get_session_factory, init_db, reset_engine
from app.knowledge.repository import KnowledgeRepository

DEFAULT_CATEGORIES = [
    ("DevOps", "DevOps 根分类", None),
    ("Kubernetes", "Kubernetes 相关知识", "DevOps"),
    ("Docker", "Docker 相关知识", "DevOps"),
    ("Linux", "Linux 系统运维", "DevOps"),
    ("Database", "数据库运维与故障", "DevOps"),
]

DEFAULT_TAGS = [
    ("k8s", "Kubernetes"),
    ("docker", "Docker"),
    ("linux", "Linux"),
    ("network", "网络"),
    ("database", "数据库"),
]


async def seed() -> None:
    """Create tables and insert default taxonomy."""
    reset_engine()
    await init_db()

    factory = get_session_factory()
    async with factory() as session:
        repo = KnowledgeRepository(session)
        name_to_id = {}

        for name, description, parent_name in DEFAULT_CATEGORIES:
            parent_id = name_to_id.get(parent_name) if parent_name else None
            category = await repo.get_or_create_category(
                name=name,
                description=description,
                parent_id=parent_id,
            )
            name_to_id[name] = category.id
            print(f"Category: {name} ({category.id})")

        for name, description in DEFAULT_TAGS:
            tag = await repo.get_or_create_tag(name=name, description=description)
            print(f"Tag: {name} ({tag.id})")

        await session.commit()

    print("Database initialized successfully.")


def main() -> None:
    asyncio.run(seed())


if __name__ == "__main__":
    main()

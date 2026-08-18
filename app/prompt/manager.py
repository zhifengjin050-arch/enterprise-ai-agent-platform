"""Prompt template manager."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.prompt.models import PromptTemplate


class PromptManager:
    """CRUD + render for DB-backed PromptTemplate rows."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        name: str,
        content: str,
        version: str = "1.0.0",
        system_prompt: Optional[str] = None,
        variables: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        tenant_id: Optional[str] = None,
    ) -> PromptTemplate:
        tpl = PromptTemplate(
            name=name,
            content=content,
            version=version,
            system_prompt=system_prompt,
            variables_json=variables or {},
            metadata_json=metadata or {},
            tenant_id=tenant_id,
        )
        self._session.add(tpl)
        await self._session.flush()
        return tpl

    async def get(self, template_id: str) -> Optional[PromptTemplate]:
        return await self._session.get(PromptTemplate, template_id)

    async def get_by_name(
        self,
        name: str,
        *,
        version: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> Optional[PromptTemplate]:
        stmt = select(PromptTemplate).where(PromptTemplate.name == name)
        if version:
            stmt = stmt.where(PromptTemplate.version == version)
        if tenant_id:
            stmt = stmt.where(PromptTemplate.tenant_id == tenant_id)
        stmt = stmt.order_by(PromptTemplate.created_at.desc()).limit(1)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list(
        self,
        *,
        tenant_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[PromptTemplate]:
        stmt = select(PromptTemplate).order_by(PromptTemplate.created_at.desc()).limit(limit)
        if tenant_id:
            stmt = stmt.where(PromptTemplate.tenant_id == tenant_id)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def render(
        self,
        name: str,
        *,
        version: Optional[str] = None,
        variables: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        tpl = await self.get_by_name(name, version=version)
        if tpl is None:
            return None
        return tpl.render(**(variables or {}))

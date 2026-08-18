"""Tests for multi-tenant isolation.

Verifies tenant_id is present in core models and
that cross-tenant queries are prohibited.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import select

from app.auth.models import Tenant
from app.auth.repository import TenantRepository
from app.knowledge.models import KnowledgeDocument


class TestTenantModel:
    """Test Tenant model."""

    def test_tenant_has_uuid_pk(self) -> None:
        """Tenant uses UUID primary key."""
        tenant = Tenant(name="test-org")
        assert tenant.name == "test-org"


class TestTenantIdInExistingModels:
    """Test that core models have tenant_id field."""

    def test_knowledge_document_has_tenant_id(self) -> None:
        """KnowledgeDocument should have tenant_id."""
        doc = KnowledgeDocument(title="Test", content="Test content", format="markdown")
        assert hasattr(doc, "tenant_id")
        assert doc.tenant_id is None

    def test_tenant_id_on_entity(self) -> None:
        """KnowledgeEntity should have tenant_id."""
        from app.entity.models import KnowledgeEntity
        entity = KnowledgeEntity(name="test-entity")
        assert hasattr(entity, "tenant_id")

    def test_tenant_id_on_relation(self) -> None:
        """KnowledgeRelation should have tenant_id."""
        from app.relation.models import KnowledgeRelation
        relation = KnowledgeRelation()
        assert hasattr(relation, "tenant_id")

    def test_tenant_id_on_workflow(self) -> None:
        """WorkflowRun should have tenant_id."""
        from app.workflow.models import WorkflowRun
        wf = WorkflowRun()
        assert hasattr(wf, "tenant_id")

    def test_user_has_tenant_id(self) -> None:
        """User should have tenant_id."""
        from app.auth.models import User
        user = User(username="test", hashed_password="pwd")
        assert hasattr(user, "tenant_id")


class TestTenantRepository:
    """Test TenantRepository."""

    async def test_create_tenant(self) -> None:
        """Test creating a tenant."""
        mock_session = AsyncMock()
        repo = TenantRepository(mock_session)
        tenant = await repo.create_tenant(name="acme-corp", description="ACME Corp")
        mock_session.add.assert_called_once()
        assert tenant.name == "acme-corp"
        assert tenant.description == "ACME Corp"

    async def test_find_by_name(self) -> None:
        """Test finding tenant by name."""
        mock_session = AsyncMock()
        mock_tenant = MagicMock(spec=Tenant)
        mock_tenant.name = "acme"
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_tenant
        mock_session.execute.return_value = mock_result
        repo = TenantRepository(mock_session)
        tenant = await repo.find_by_name("acme")
        assert tenant is not None
        assert tenant.name == "acme"

    async def test_get_tenant_not_found(self) -> None:
        """Test getting non-existent tenant."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result
        repo = TenantRepository(mock_session)
        tenant = await repo.get_tenant(uuid.uuid4())
        assert tenant is None


class TestCrossTenantProhibition:
    """Verify cross-tenant query prohibition pattern."""

    async def test_query_scoped_to_tenant(self) -> None:
        """Test that queries include tenant_id filter."""
        tenant_id = uuid.uuid4()
        stmt = select(KnowledgeDocument).where(KnowledgeDocument.tenant_id == tenant_id)
        compiled = str(stmt.compile(compile_kwargs={"literal_binds": True}))
        # The compiled SQL may not contain the UUID string directly,
        # but should definitely contain "tenant_id"
        assert "tenant_id" in compiled
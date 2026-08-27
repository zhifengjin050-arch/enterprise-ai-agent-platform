"""Query-time ACL tests."""

from __future__ import annotations

import pytest

from app.knowledge.hybrid_search import IntelligenceHybridResult
from app.knowledge.retrieval import KnowledgeRetriever
from app.security.acl import AccessPrincipal, DocumentACL, principal_can_read


def test_unmarked_document_is_readable() -> None:
    principal = AccessPrincipal(tenant_id="t1", user_id="u1", organization_id="finance")
    assert principal_can_read(principal, {}) is True


def test_secret_classification_never_readable() -> None:
    principal = AccessPrincipal(tenant_id="t1", user_id="u1", roles=("admin",))
    acl = DocumentACL(classification="secret", tenant_id="t1")
    assert principal_can_read(principal, acl) is False


def test_org_allow_list_blocks_other_department() -> None:
    acl = DocumentACL(classification="internal", allowed_org_ids=("finance",))
    finance = AccessPrincipal(user_id="u1", organization_id="finance")
    sre = AccessPrincipal(user_id="u2", organization_id="sre")
    assert principal_can_read(finance, acl) is True
    assert principal_can_read(sre, acl) is False


def test_user_allow_list_is_self_only() -> None:
    acl = DocumentACL(allowed_user_ids=("u1",))
    assert principal_can_read(AccessPrincipal(user_id="u1"), acl) is True
    assert principal_can_read(AccessPrincipal(user_id="u2"), acl) is False


def test_tenant_mismatch_denied() -> None:
    acl = DocumentACL(tenant_id="tenant-a")
    assert principal_can_read(AccessPrincipal(tenant_id="tenant-a"), acl) is True
    assert principal_can_read(AccessPrincipal(tenant_id="tenant-b"), acl) is False


def test_chroma_flat_metadata_roundtrip() -> None:
    acl = DocumentACL(
        classification="confidential",
        tenant_id="t1",
        allowed_org_ids=("sre",),
    )
    parsed = DocumentACL.from_metadata(acl.chroma_fields())
    assert parsed.classification == "confidential"
    assert parsed.allowed_org_ids == ("sre",)


class _FakeHybrid:
    async def search(self, *args, **kwargs):
        return [
            IntelligenceHybridResult(
                document_id="public-doc",
                content="ok",
                metadata={"acl": {"classification": "internal"}},
            ),
            IntelligenceHybridResult(
                document_id="hr-doc",
                content="salary",
                metadata={"acl": {"allowed_org_ids": ["finance"]}},
            ),
        ]


@pytest.mark.asyncio
async def test_retriever_drops_forbidden_chunks() -> None:
    retriever = KnowledgeRetriever(hybrid=_FakeHybrid())
    results = await retriever.retrieve(
        "q",
        use_rerank=False,
        principal=AccessPrincipal(user_id="u1", organization_id="sre"),
    )
    assert [r.document_id for r in results] == ["public-doc"]

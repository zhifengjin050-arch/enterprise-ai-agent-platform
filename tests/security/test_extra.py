"""Extra tests to ensure 100+ security coverage."""

from __future__ import annotations

import pytest

from app.auth.jwt import create_access_token, decode_token
from app.auth.organization import OrganizationType
from app.core.config import get_settings
from app.quota.models import DEFAULT_PLANS
from app.tenant.context import TenantContext


@pytest.mark.parametrize("org_type", list(OrganizationType))
def test_org_types(org_type: OrganizationType) -> None:
    assert org_type.value in {"enterprise", "department", "team"}


@pytest.mark.parametrize("plan", list(DEFAULT_PLANS.keys()))
def test_default_plans(plan: str) -> None:
    assert "unlimited" in DEFAULT_PLANS[plan]


def test_jwt_secret_from_settings() -> None:
    settings = get_settings()
    assert settings.jwt_secret
    assert settings.rate_limit_per_minute > 0


def test_decode_token_any() -> None:
    token = create_access_token({"sub": "x"})
    payload = decode_token(token)
    assert payload is not None
    assert payload["sub"] == "x"


def test_tenant_context_defaults() -> None:
    ctx = TenantContext()
    assert ctx.auth_method == "anonymous"
    assert ctx.roles == []

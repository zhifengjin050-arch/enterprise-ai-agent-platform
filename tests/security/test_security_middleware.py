"""Security middleware + migration + package smoke tests."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from app.core.middleware.security import SecurityMiddleware
from app.tenant import TenantContext, TenantMiddleware, apply_tenant_filter


class TestSecurityMiddleware:
    def test_client_ip_from_forwarded(self) -> None:
        mw = SecurityMiddleware(app=None)  # type: ignore[arg-type]
        class R:
            headers = {"X-Forwarded-For": "1.2.3.4, 5.6.7.8"}
            client = None
        assert mw._client_ip(R()) == "1.2.3.4"

    def test_rate_limit(self) -> None:
        mw = SecurityMiddleware(app=None, rate_limit=3, rate_window_seconds=60)  # type: ignore[arg-type]
        assert mw._allow("ip1")
        assert mw._allow("ip1")
        assert mw._allow("ip1")
        assert mw._allow("ip1") is False

    @pytest.mark.asyncio
    async def test_cors_headers(self, api_client) -> None:
        resp = await api_client.get(
            "/api/health", headers={"Origin": "http://localhost"}
        )
        assert resp.status_code == 200
        assert "access-control-allow-origin" in {k.lower() for k in resp.headers.keys()}

    @pytest.mark.asyncio
    async def test_security_routes_registered(self, api_client) -> None:
        paths = (await api_client.get("/openapi.json")).json()["paths"]
        for p in (
            "/api/users",
            "/api/roles",
            "/api/permissions",
            "/api/api-keys",
            "/api/audit/logs",
            "/api/quota/status",
            "/api/organizations",
            "/api/auth/refresh",
        ):
            assert p in paths


class TestMigration0009:
    def test_revision(self) -> None:
        path = (
            Path(__file__).resolve().parents[2]
            / "alembic"
            / "versions"
            / "0009_enterprise_security.py"
        )
        spec = importlib.util.spec_from_file_location("mig_0009", path)
        mod = importlib.util.module_from_spec(spec)
        assert spec and spec.loader
        spec.loader.exec_module(mod)
        assert mod.revision == "0009_enterprise_security"
        assert mod.down_revision == "0008_agent_runtime"
        assert callable(mod.upgrade)


class TestPackageExports:
    def test_tenant_exports(self) -> None:
        assert TenantContext is not None
        assert TenantMiddleware is not None
        assert apply_tenant_filter is not None

    def test_imports(self) -> None:
        from app.api_key import ApiKeyService
        from app.audit import AuditEvent
        from app.quota import QuotaService
        from app.auth import PermissionChecker, create_refresh_token

        assert ApiKeyService and AuditEvent and QuotaService
        assert PermissionChecker and create_refresh_token

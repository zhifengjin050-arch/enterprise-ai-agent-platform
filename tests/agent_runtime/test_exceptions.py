"""Extra coverage: exceptions, package exports, permissions."""

from __future__ import annotations

import pytest

from app.core.exceptions import (
    AgentException,
    AgentPermissionException,
    ToolPermissionException,
    LLMQuotaException,
    AgentNotFoundException,
    ToolNotFoundException,
    AgentExecutionException,
)
from app.auth.models import PERMISSION_CODES
from app.agent_runtime import (
    BaseAgent,
    TaskPlanner,
    AgentMemoryManager,
    AgentTrace,
    ContextEngine,
    AgentResult,
)
from app.llm import LLMGateway, ModelRouter, TaskComplexity, get_llm_gateway
from app.prompt import PromptTemplate, PromptManager


class TestAgentExceptions:
    @pytest.mark.parametrize(
        "exc_cls,code",
        [
            (AgentException, "AGENT_ERROR"),
            (AgentPermissionException, "AGENT_PERMISSION_DENIED"),
            (ToolPermissionException, "TOOL_PERMISSION_DENIED"),
            (LLMQuotaException, "LLM_QUOTA_EXCEEDED"),
            (AgentNotFoundException, "AGENT_NOT_FOUND"),
            (ToolNotFoundException, "TOOL_NOT_FOUND"),
            (AgentExecutionException, "AGENT_EXECUTION_FAILED"),
        ],
    )
    def test_codes(self, exc_cls, code: str) -> None:
        e = exc_cls()
        assert e.code == code
        d = e.to_dict()
        assert d["code"] == code

    def test_custom_message(self) -> None:
        e = AgentNotFoundException(message="missing", details={"id": "1"})
        assert e.message == "missing"
        assert e.details["id"] == "1"

    def test_http_status(self) -> None:
        assert AgentPermissionException().http_status == 403
        assert LLMQuotaException().http_status == 429
        assert AgentNotFoundException().http_status == 404


class TestPermissions:
    @pytest.mark.parametrize(
        "code",
        ["agent.read", "agent.write", "agent.execute"],
    )
    def test_agent_permissions_registered(self, code: str) -> None:
        assert code in PERMISSION_CODES


class TestPackageExports:
    def test_runtime_exports(self) -> None:
        assert BaseAgent is not None
        assert TaskPlanner is not None
        assert AgentMemoryManager is not None
        assert AgentTrace is not None
        assert ContextEngine is not None
        assert AgentResult is not None

    def test_llm_exports(self) -> None:
        assert LLMGateway is not None
        assert ModelRouter is not None
        assert TaskComplexity.SIMPLE
        assert get_llm_gateway() is not None

    def test_prompt_exports(self) -> None:
        assert PromptTemplate is not None
        assert PromptManager is not None


class TestMigrationAndCompile:
    def test_migration_module_importable(self) -> None:
        import importlib.util
        from pathlib import Path

        path = (
            Path(__file__).resolve().parents[2]
            / "alembic"
            / "versions"
            / "0008_agent_runtime.py"
        )
        spec = importlib.util.spec_from_file_location("mig_0008", path)
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        assert mod.revision == "0008_agent_runtime"
        assert mod.down_revision == "0007_add_document_chunks"

    def test_upgrade_downgrade_callable(self) -> None:
        import importlib.util
        from pathlib import Path

        path = (
            Path(__file__).resolve().parents[2]
            / "alembic"
            / "versions"
            / "0008_agent_runtime.py"
        )
        spec = importlib.util.spec_from_file_location("mig_0008b", path)
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        assert callable(mod.upgrade)
        assert callable(mod.downgrade)

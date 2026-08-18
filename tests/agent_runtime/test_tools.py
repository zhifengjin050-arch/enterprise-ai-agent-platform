"""Tests for Tool System."""

from __future__ import annotations

import pytest

from app.agent_runtime.tools.base import ToolContext, ToolResult
from app.agent_runtime.tools.registry import ToolRegistry, build_default_registry
from app.agent_runtime.tools.knowledge_search import KnowledgeSearchTool
from app.agent_runtime.tools.graph_query import GraphQueryTool
from app.agent_runtime.tools.document_query import DocumentQueryTool
from app.agent_runtime.tools.connector_sync import ConnectorSyncTool
from app.core.exceptions import ToolNotFoundException, ToolPermissionException
from tests.agent_runtime.conftest import StubTool


class TestToolResult:
    def test_to_dict(self) -> None:
        r = ToolResult(success=True, data={"a": 1}, error="", metadata={"x": 1})
        d = r.to_dict()
        assert d["success"] is True
        assert d["data"]["a"] == 1

    def test_failure(self) -> None:
        r = ToolResult(success=False, error="boom")
        assert r.success is False


class TestToolContext:
    def test_defaults(self) -> None:
        ctx = ToolContext()
        assert ctx.tenant_id is None
        assert ctx.task_id == ""
        assert ctx.metadata == {}


class TestToolRegistry:
    def test_register_and_get(self) -> None:
        reg = ToolRegistry()
        tool = StubTool(name="t1")
        reg.register(tool)
        assert reg.get("t1") is tool

    def test_duplicate_register_raises(self) -> None:
        reg = ToolRegistry()
        reg.register(StubTool(name="t1"))
        with pytest.raises(ValueError):
            reg.register(StubTool(name="t1"))

    def test_unregister(self) -> None:
        reg = ToolRegistry()
        reg.register(StubTool(name="t1"))
        reg.unregister("t1")
        assert reg.get("t1") is None

    def test_list_tools(self) -> None:
        reg = ToolRegistry()
        reg.register(StubTool(name="a"))
        reg.register(StubTool(name="b"))
        names = {t["name"] for t in reg.list_tools()}
        assert names == {"a", "b"}

    def test_discover_all(self) -> None:
        reg = ToolRegistry()
        reg.register(StubTool(name="knowledge_search"))
        reg.register(StubTool(name="graph_query"))
        assert set(reg.discover()) == {"knowledge_search", "graph_query"}

    def test_discover_keyword(self) -> None:
        reg = ToolRegistry()
        reg.register(StubTool(name="knowledge_search"))
        reg.register(StubTool(name="graph_query"))
        assert reg.discover("knowledge") == ["knowledge_search"]

    @pytest.mark.asyncio
    async def test_execute_success(self) -> None:
        reg = ToolRegistry()
        reg.register(StubTool(name="stub_tool", data=[1, 2]))
        result = await reg.execute("stub_tool", {"q": "x"})
        assert result.success
        assert result.data == [1, 2]

    @pytest.mark.asyncio
    async def test_execute_not_found(self) -> None:
        reg = ToolRegistry()
        with pytest.raises(ToolNotFoundException):
            await reg.execute("missing", {})

    @pytest.mark.asyncio
    async def test_execute_permission_denied(self) -> None:
        reg = ToolRegistry()
        reg.register(StubTool(name="stub_tool", permissions=["admin.users"]))
        with pytest.raises(ToolPermissionException):
            await reg.execute(
                "stub_tool",
                {},
                allowed_permissions=["knowledge.read"],
            )

    @pytest.mark.asyncio
    async def test_execute_permission_ok(self) -> None:
        reg = ToolRegistry()
        reg.register(StubTool(name="stub_tool", permissions=["knowledge.read"]))
        result = await reg.execute(
            "stub_tool",
            {},
            allowed_permissions=["knowledge.read", "agent.execute"],
        )
        assert result.success

    def test_build_default_registry(self) -> None:
        reg = build_default_registry()
        names = set(reg.discover())
        assert "knowledge_search" in names
        assert "graph_query" in names
        assert "document_query" in names
        assert "connector_sync" in names

    def test_tool_to_dict(self) -> None:
        tool = StubTool()
        d = tool.to_dict()
        assert d["name"] == "stub_tool"
        assert "permissions" in d


class TestBuiltinToolsValidation:
    @pytest.mark.asyncio
    async def test_knowledge_search_requires_query(self) -> None:
        tool = KnowledgeSearchTool()
        result = await tool.execute({}, ToolContext())
        assert result.success is False
        assert "query" in result.error

    @pytest.mark.asyncio
    async def test_document_query_requires_id(self) -> None:
        tool = DocumentQueryTool()
        result = await tool.execute({}, ToolContext())
        assert result.success is False

    @pytest.mark.asyncio
    async def test_document_query_requires_session(self) -> None:
        tool = DocumentQueryTool()
        result = await tool.execute({"document_id": "x"}, ToolContext())
        assert result.success is False
        assert "session" in result.error.lower()

    @pytest.mark.asyncio
    async def test_graph_query_requires_entity(self) -> None:
        tool = GraphQueryTool()
        result = await tool.execute({}, ToolContext())
        assert result.success is False

    @pytest.mark.asyncio
    async def test_connector_sync_requires_id(self) -> None:
        tool = ConnectorSyncTool()
        result = await tool.execute({}, ToolContext())
        assert result.success is False

    @pytest.mark.parametrize(
        "tool_cls",
        [KnowledgeSearchTool, GraphQueryTool, DocumentQueryTool, ConnectorSyncTool],
    )
    def test_builtin_have_name_and_permissions(self, tool_cls) -> None:
        tool = tool_cls()
        assert tool.name
        assert isinstance(tool.permissions, list)
        assert tool.description

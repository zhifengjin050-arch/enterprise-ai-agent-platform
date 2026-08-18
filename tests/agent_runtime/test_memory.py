"""Tests for Agent Memory, Trace, Context, Prompt."""

from __future__ import annotations

import pytest

from app.agent_runtime.memory import AgentMemoryManager
from app.agent_runtime.trace import AgentTrace
from app.agent_runtime.context import ContextEngine
from app.agent_runtime.models import (
    AgentRecord,
    AgentResult,
    AgentStatus,
    AgentTask,
    AgentTaskStatus,
    AgentMessage,
    AgentToolCall,
    ExecutionPlan,
    PlanStep,
)
from app.prompt.manager import PromptManager
from app.prompt.models import PromptTemplate


class TestAgentMemory:
    def test_short_term_turns(self) -> None:
        mem = AgentMemoryManager(max_turns=10)
        cid = "c1"
        for i in range(12):
            mem.add_user_message(cid, f"u{i}")
            mem.add_assistant_message(cid, f"a{i}")
        # ConversationMemory trims to max_turns messages
        conv = mem.conversation.get_conversation(cid)
        assert conv is not None
        assert len(conv.messages) <= 10

    def test_prompt_context(self) -> None:
        mem = AgentMemoryManager()
        mem.add_user_message("c1", "你好")
        mem.add_assistant_message("c1", "您好")
        ctx = mem.prompt_context("c1")
        assert "你好" in ctx

    def test_ensure_conversation(self) -> None:
        mem = AgentMemoryManager()
        c = mem.ensure_conversation("new", user_id="u1")
        assert c.id == "new"

    def test_knowledge_memory_access(self) -> None:
        mem = AgentMemoryManager()
        mem.knowledge.remember_retrieval("s1", "q", [{"id": "1"}])
        assert mem.knowledge is not None

    @pytest.mark.asyncio
    async def test_persist_and_list(self, db_session) -> None:
        mem = AgentMemoryManager()
        # Need an agent for FK? agent_id optional — but FK allows null
        await mem.persist_message(
            db_session,
            conversation_id="conv-1",
            role="user",
            content="hello",
            tenant_id="t1",
        )
        await mem.persist_message(
            db_session,
            conversation_id="conv-1",
            role="assistant",
            content="hi",
            tenant_id="t1",
        )
        history = await mem.list_history(db_session, "conv-1")
        assert len(history) == 2
        assert history[0]["role"] == "user"


class TestAgentTrace:
    def test_lifecycle(self) -> None:
        t = AgentTrace()
        t.start(task_id="tid", agent="A", agent_type="knowledge")
        t.record_tool("knowledge_search", latency_ms=12, success=True)
        t.record_model("deepseek", tokens=100)
        t.finish(success=True)
        d = t.to_dict()
        assert d["task_id"] == "tid"
        assert d["model"] == "deepseek"
        assert d["tokens"] == 100
        assert d["success"] is True
        assert len(d["tools"]) == 1
        assert d["latency_ms"] >= 0

    def test_finish_with_error(self) -> None:
        t = AgentTrace()
        t.start(task_id="t", agent="A")
        t.finish(success=False, error="boom")
        assert t.error == "boom"


class TestContextEngine:
    def test_build_basic(self) -> None:
        eng = ContextEngine()
        out = eng.build(
            query="Q",
            conversation_context="用户: hi",
            sources=[{"title": "Doc", "content": "body"}],
        )
        assert "Q" in out["user"]
        assert "Doc" in out["sources_block"]
        assert out["system"]

    def test_build_empty_sources(self) -> None:
        eng = ContextEngine()
        out = eng.build(query="Q")
        assert "无检索" in out["sources_block"]

    def test_max_chars_truncates(self) -> None:
        eng = ContextEngine(max_source_chars=50)
        sources = [{"title": f"T{i}", "content": "x" * 100} for i in range(10)]
        out = eng.build(query="Q", sources=sources)
        assert len(out["sources_block"]) <= 200


class TestPromptManager:
    @pytest.mark.asyncio
    async def test_create_and_render(self, db_session) -> None:
        mgr = PromptManager(db_session)
        tpl = await mgr.create(
            name="agent_system",
            content="Hello {name}",
            version="1.0.0",
            system_prompt="sys",
            variables={"name": "str"},
        )
        assert tpl.id
        rendered = await mgr.render("agent_system", variables={"name": "World"})
        assert rendered == "Hello World"

    @pytest.mark.asyncio
    async def test_get_by_name_version(self, db_session) -> None:
        mgr = PromptManager(db_session)
        await mgr.create(name="p", content="v1", version="1.0.0")
        await mgr.create(name="p", content="v2", version="2.0.0")
        t = await mgr.get_by_name("p", version="2.0.0")
        assert t is not None
        assert t.content == "v2"

    @pytest.mark.asyncio
    async def test_list(self, db_session) -> None:
        mgr = PromptManager(db_session)
        await mgr.create(name="a", content="c")
        await mgr.create(name="b", content="c")
        items = await mgr.list()
        assert len(items) >= 2

    @pytest.mark.asyncio
    async def test_render_missing(self, db_session) -> None:
        mgr = PromptManager(db_session)
        assert await mgr.render("missing") is None

    def test_template_render_partial(self) -> None:
        tpl = PromptTemplate(name="n", version="1", content="Hi {a} {b}")
        # Missing b — format fails, fallback replace
        out = tpl.render(a="1")
        assert "1" in out

    def test_template_to_dict(self) -> None:
        tpl = PromptTemplate(name="n", version="1.0.0", content="c")
        d = tpl.to_dict()
        assert d["name"] == "n"


class TestModelsDTO:
    def test_agent_result(self) -> None:
        r = AgentResult(success=True, answer="a", sources=[], tool_calls=[], task_id="1")
        assert r.to_dict()["answer"] == "a"

    def test_execution_plan(self) -> None:
        p = ExecutionPlan(steps=[PlanStep(1, "knowledge_search")], query="q")
        assert p.to_dict()["query"] == "q"

    def test_agent_status_enum(self) -> None:
        assert AgentStatus.RUNNING.value == "running"
        assert AgentTaskStatus.PENDING.value == "pending"

    @pytest.mark.asyncio
    async def test_orm_agent_record(self, db_session) -> None:
        rec = AgentRecord(name="A1", agent_type="knowledge", tenant_id="t1")
        db_session.add(rec)
        await db_session.flush()
        assert rec.id
        assert rec.to_dict()["name"] == "A1"

    @pytest.mark.asyncio
    async def test_orm_task_fk(self, db_session) -> None:
        rec = AgentRecord(name="A1", agent_type="knowledge")
        db_session.add(rec)
        await db_session.flush()
        task = AgentTask(agent_id=rec.id, agent_type="knowledge", input_json={"q": "1"})
        db_session.add(task)
        await db_session.flush()
        assert task.to_dict()["agent_id"] == rec.id

    @pytest.mark.asyncio
    async def test_orm_tool_call(self, db_session) -> None:
        rec = AgentRecord(name="A1", agent_type="knowledge")
        db_session.add(rec)
        await db_session.flush()
        task = AgentTask(agent_id=rec.id, agent_type="knowledge")
        db_session.add(task)
        await db_session.flush()
        call = AgentToolCall(
            task_id=task.id,
            tool_name="knowledge_search",
            input_json={"query": "x"},
            status="success",
            latency_ms=10,
        )
        db_session.add(call)
        await db_session.flush()
        assert call.to_dict()["tool_name"] == "knowledge_search"

    @pytest.mark.asyncio
    async def test_orm_message(self, db_session) -> None:
        msg = AgentMessage(
            conversation_id="c1",
            role="user",
            content="hi",
        )
        db_session.add(msg)
        await db_session.flush()
        assert msg.to_dict()["role"] == "user"

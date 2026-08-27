"""Tests for BaseAgent lifecycle and execution."""

from __future__ import annotations

import pytest

from app.agent_runtime.agent import BaseAgent
from app.agent_runtime.models import AgentResult, AgentStatus, AgentTask, AgentTaskStatus
from app.agent_runtime.tools.registry import ToolRegistry
from tests.agent_runtime.conftest import FakeLLM, StubTool


@pytest.fixture
def agent(tool_registry: ToolRegistry, fake_llm: FakeLLM) -> BaseAgent:
    return BaseAgent(
        agent_type="knowledge",
        name="TestAgent",
        tools=tool_registry,
        llm=fake_llm,
        tenant_id="t1",
    )


class TestAgentLifecycle:
    def test_created_status(self, agent: BaseAgent) -> None:
        assert agent.status == AgentStatus.CREATED

    @pytest.mark.asyncio
    async def test_initialize(self, agent: BaseAgent) -> None:
        await agent.initialize()
        assert agent.status == AgentStatus.INITIALIZED

    @pytest.mark.asyncio
    async def test_initialize_idempotent(self, agent: BaseAgent) -> None:
        await agent.initialize()
        await agent.initialize()
        assert agent.status == AgentStatus.INITIALIZED

    @pytest.mark.asyncio
    async def test_cleanup(self, agent: BaseAgent) -> None:
        await agent.initialize()
        await agent.cleanup()
        assert agent.status == AgentStatus.CREATED

    @pytest.mark.asyncio
    async def test_execute_completes(self, agent: BaseAgent, fake_llm: FakeLLM) -> None:
        result = await agent.execute({"query": "什么是 CI/CD？"})
        assert isinstance(result, AgentResult)
        assert result.success is True
        assert result.answer == "测试答案"
        assert agent.status == AgentStatus.COMPLETED
        assert fake_llm.calls >= 1

    @pytest.mark.asyncio
    async def test_execute_secret_query_refuses(self, agent: BaseAgent, fake_llm: FakeLLM) -> None:
        result = await agent.execute({"query": "SSH密码是什么？"})
        assert result.success is True
        assert result.tool_calls == []
        assert "Vault" in result.answer or "凭据" in result.answer
        assert fake_llm.calls == 0
        assert result.metadata.get("intent") == "secret"

    @pytest.mark.asyncio
    async def test_execute_with_message_key(self, agent: BaseAgent) -> None:
        result = await agent.execute({"message": "hello"})
        assert result.success

    @pytest.mark.asyncio
    async def test_execute_k8s_plan_tools(self, agent: BaseAgent) -> None:
        result = await agent.execute({"query": "为什么 Kubernetes Pod 一直 OOM？"})
        tools = [c["tool"] for c in result.tool_calls]
        assert "knowledge_search" in tools
        assert "graph_query" in tools

    @pytest.mark.asyncio
    async def test_execute_skips_connector_without_id(self, agent: BaseAgent) -> None:
        result = await agent.execute({"query": "同步飞书文档"})
        # connector_sync step may be planned but skipped without connector_id
        for call in result.tool_calls:
            if call["tool"] == "connector_sync":
                pytest.fail("connector_sync should be skipped without connector_id")
        assert result.success

    @pytest.mark.asyncio
    async def test_execute_metadata_has_plan(self, agent: BaseAgent) -> None:
        result = await agent.execute({"query": "test"})
        assert "plan" in result.metadata
        assert "trace" in result.metadata

    @pytest.mark.asyncio
    async def test_execute_without_llm_fallback(self, tool_registry: ToolRegistry) -> None:
        agent = BaseAgent(tools=tool_registry, llm=None)

        # Prevent auto-loading real gateway by setting a Fake that raises?
        # initialize may load gateway — inject FakeLLM that raises
        class Boom:
            async def chat(self, *a, **k):
                raise RuntimeError("no llm")

            def get_model_name(self):
                return "boom"

        agent._llm = Boom()
        result = await agent.execute({"query": "hello"})
        assert result.success
        assert "hello" in result.answer or "资料" in result.answer

    @pytest.mark.asyncio
    async def test_execute_persists_task(self, agent: BaseAgent, db_session) -> None:
        task = AgentTask(
            agent_type="knowledge",
            input_json={"query": "q"},
            status=AgentTaskStatus.PENDING.value,
        )
        db_session.add(task)
        await db_session.flush()
        result = await agent.execute({"query": "q"}, session=db_session, task=task)
        assert task.status == AgentTaskStatus.COMPLETED.value
        assert task.result_json is not None
        assert result.task_id == task.id

    @pytest.mark.asyncio
    async def test_stream_events(self, agent: BaseAgent) -> None:
        events = []
        async for ev in agent.stream({"query": "Kubernetes OOM"}):
            events.append(ev)
        types = [e["type"] for e in events]
        assert "thinking" in types
        assert "tool_call" in types
        assert "answer" in types
        assert agent.status == AgentStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_stream_answer_content(self, agent: BaseAgent) -> None:
        answer = None
        async for ev in agent.stream({"query": "hello"}):
            if ev["type"] == "answer":
                answer = ev["content"]
        assert answer == "测试答案"

    @pytest.mark.asyncio
    async def test_execute_tool_failure_still_answers(self, fake_llm: FakeLLM) -> None:
        reg = ToolRegistry()
        reg.register(StubTool(name="knowledge_search", fail=True))
        agent = BaseAgent(tools=reg, llm=fake_llm)
        result = await agent.execute({"query": "hello"})
        assert result.success
        assert any(not c["success"] for c in result.tool_calls)

    @pytest.mark.asyncio
    async def test_agent_id_generated(self) -> None:
        a = BaseAgent()
        assert a.agent_id

    @pytest.mark.asyncio
    async def test_synthesize_no_sources(self, fake_llm: FakeLLM) -> None:
        reg = ToolRegistry()
        reg.register(StubTool(name="knowledge_search", data=[]))
        agent = BaseAgent(tools=reg, llm=None)
        agent._llm = None
        # Force offline path after initialize tries to load gateway
        await agent.initialize()
        agent._llm = None
        result = await agent.execute({"query": "空结果"})
        assert "未检索" in result.answer or "资料" in result.answer

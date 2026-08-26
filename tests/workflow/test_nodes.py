"""Tests for workflow node implementations — Phase 9."""

from __future__ import annotations

import pytest

from app.workflow_engine.nodes import (
    AgentNode,
    ApprovalNode,
    ConditionNode,
    EndNode,
    NodeContext,
    NodeFactory,
    ToolNode,
    TriggerNode,
)


@pytest.fixture
def context() -> NodeContext:
    return NodeContext(
        workflow_id="wf-1",
        run_id="run-1",
        tenant_id="tenant-1",
        triggered_by="test",
        variables={"input": "hello", "score": 0.8},
    )


class TestTriggerNode:
    async def test_execute_success(self, context: NodeContext) -> None:
        node = TriggerNode(name="start", config={"payload": {"key": "val"}})
        result = await node.execute(context)
        assert result["status"] == "success"
        assert result["output"]["triggered"] is True
        assert context.get("key") == "val"

    async def test_execute_empty_payload(self, context: NodeContext) -> None:
        node = TriggerNode(name="start")
        result = await node.execute(context)
        assert result["status"] == "success"

    async def test_execute_async(self, context: NodeContext) -> None:
        node = TriggerNode(name="start")
        result = await node.execute(context)
        assert result["status"] == "success"


class TestAgentNode:
    async def test_execute_success(self, context: NodeContext) -> None:
        node = AgentNode(
            name="analysis",
            config={"agent_name": "test_agent", "task": "analyze {{input}}"},
        )
        result = await node.execute(context)
        assert result["status"] == "success"
        assert "agent" in result["output"]

    async def test_stores_output_in_context(self, context: NodeContext) -> None:
        node = AgentNode(
            name="analysis",
            config={
                "agent_name": "test_agent",
                "task": "analyze",
                "output_key": "analysis_result",
            },
        )
        await node.execute(context)
        assert context.get("analysis_result") is not None

    async def test_uses_input_key(self, context: NodeContext) -> None:
        node = AgentNode(
            name="analysis",
            config={
                "agent_name": "test_agent",
                "input_key": "input",
            },
        )
        result = await node.execute(context)
        assert result["status"] == "success"


class TestToolNode:
    async def test_execute_success(self, context: NodeContext) -> None:
        node = ToolNode(
            name="restart",
            config={"tool_name": "k8s_restart", "params": {"namespace": "default"}},
        )
        result = await node.execute(context)
        assert result["status"] == "success"
        assert "tool" in result["output"]

    async def test_variable_interpolation(self, context: NodeContext) -> None:
        node = ToolNode(
            name="restart",
            config={
                "tool_name": "k8s_restart",
                "params": {"namespace": "{{input}}", "pod": "web-1"},
            },
        )
        result = await node.execute(context)
        assert result["status"] == "success"

    async def test_empty_params(self, context: NodeContext) -> None:
        node = ToolNode(name="restart", config={"tool_name": "k8s_restart"})
        result = await node.execute(context)
        assert result["status"] == "success"


class TestConditionNode:
    async def test_true_branch(self, context: NodeContext) -> None:
        node = ConditionNode(
            name="check",
            config={
                "expression": "score > 0.5",
                "true_next": "process",
                "false_next": "reject",
            },
        )
        result = await node.execute(context)
        assert result["status"] == "success"
        assert result["output"]["condition_result"] is True
        assert node.get_next_node(result) == "process"

    async def test_false_branch(self, context: NodeContext) -> None:
        context.set("score", 0.3)
        node = ConditionNode(
            name="check",
            config={
                "expression": "score > 0.5",
                "true_next": "process",
                "false_next": "reject",
            },
        )
        result = await node.execute(context)
        assert result["status"] == "success"
        assert result["output"]["condition_result"] is False
        assert node.get_next_node(result) == "reject"

    async def test_complex_expression(self, context: NodeContext) -> None:
        node = ConditionNode(
            name="check",
            config={
                "expression": "len(input) > 3 and score > 0.5",
                "true_next": "yes",
                "false_next": "no",
            },
        )
        result = await node.execute(context)
        assert result["output"]["condition_result"] is True

    async def test_expression_error_falls_to_false(self, context: NodeContext) -> None:
        node = ConditionNode(
            name="check",
            config={
                "expression": "undefined_var > 0",
                "true_next": "yes",
                "false_next": "no",
            },
        )
        result = await node.execute(context)
        assert result["status"] == "failure"

    async def test_node_referenced_by_config(self) -> None:
        """ConditionNode can store next in config or be set externally."""
        node = ConditionNode(
            name="check",
            config={"expression": "True", "true_next": "a", "false_next": "b"},
        )
        ctx = NodeContext(workflow_id="w", run_id="r")
        result = await node.execute(ctx)
        assert result["output"]["condition_result"] is True
        assert node.get_next_node(result) == "a"


class TestApprovalNode:
    async def test_execute_returns_waiting(self, context: NodeContext) -> None:
        node = ApprovalNode(
            name="review",
            config={"approvers": ["admin"], "message": "Approve this?"},
        )
        result = await node.execute(context)
        assert result["status"] == "waiting"
        assert "approval_id" in result["output"]

    async def test_stores_approvers_and_message(self, context: NodeContext) -> None:
        node = ApprovalNode(
            name="review",
            config={"approvers": ["admin", "manager"], "message": "Please approve"},
        )
        result = await node.execute(context)
        assert result["output"]["approvers"] == ["admin", "manager"]
        assert result["output"]["message"] == "Please approve"


class TestEndNode:
    async def test_execute_success(self, context: NodeContext) -> None:
        node = EndNode(name="finish")
        result = await node.execute(context)
        assert result["status"] == "success"
        assert result["output"]["completed"] is True

    async def test_reports_node_count(self, context: NodeContext) -> None:
        context.record_result("step1", {"status": "success"})
        context.record_result("step2", {"status": "success"})
        node = EndNode(name="finish")
        result = await node.execute(context)
        assert result["output"]["node_count"] == 2
        assert "final_variables" in result["output"]


class TestNodeFactory:
    def test_create_trigger(self) -> None:
        node = NodeFactory.create_node("trigger", "start")
        assert isinstance(node, TriggerNode)

    def test_create_agent(self) -> None:
        node = NodeFactory.create_node("agent", "a", {"agent_name": "test"})
        assert isinstance(node, AgentNode)

    def test_create_tool(self) -> None:
        node = NodeFactory.create_node("tool", "t", {"tool_name": "test"})
        assert isinstance(node, ToolNode)

    def test_create_condition(self) -> None:
        node = NodeFactory.create_node("condition", "c", {"expression": "True"})
        assert isinstance(node, ConditionNode)

    def test_create_approval(self) -> None:
        node = NodeFactory.create_node("approval", "ap", {"approvers": ["admin"]})
        assert isinstance(node, ApprovalNode)

    def test_create_end(self) -> None:
        node = NodeFactory.create_node("end", "finish")
        assert isinstance(node, EndNode)

    def test_unknown_type_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown node type"):
            NodeFactory.create_node("unknown", "x")

    def test_passes_config(self) -> None:
        config = {"agent_name": "my_agent", "task": "do something"}
        node = NodeFactory.create_node("agent", "a", config)
        assert node.config["agent_name"] == "my_agent"

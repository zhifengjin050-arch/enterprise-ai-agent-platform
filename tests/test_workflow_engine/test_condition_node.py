"""ConditionNode uses safe_eval instead of unrestricted eval."""

from __future__ import annotations

import pytest

from app.workflow_engine.nodes import ConditionNode, NodeContext


def _ctx(**variables):
    return NodeContext(
        workflow_id="wf",
        run_id="run",
        variables=variables,
    )


@pytest.mark.asyncio
async def test_condition_true_branch() -> None:
    node = ConditionNode(
        "gate", {"expression": "score > 0.5", "true_next": "ok", "false_next": "no"}
    )
    result = await node.execute(_ctx(score=0.8))
    assert result["output"]["condition_result"] is True
    assert result["_next_node"] == "ok"


@pytest.mark.asyncio
async def test_condition_rejects_unsafe_expression() -> None:
    node = ConditionNode(
        "gate",
        {"expression": "__import__('os').popen('id')", "true_next": "ok", "false_next": "no"},
    )
    result = await node.execute(_ctx())
    assert result["status"] == "failure"
    assert result["_next_node"] == "no"

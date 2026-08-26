"""Tests for Workflow JSON DSL parser — Phase 9."""

from __future__ import annotations

from typing import Any, Dict

import pytest

from app.workflow_engine.nodes import (
    AgentNode,
    ApprovalNode,
    ConditionNode,
    EndNode,
    ToolNode,
    TriggerNode,
)
from app.workflow_engine.parser import WorkflowParser, WorkflowValidationError


class TestParseDefinition:
    """Tests for WorkflowParser.parse_definition."""

    def test_valid_minimal(self, sample_workflow_definition: Dict[str, Any]) -> None:
        result = WorkflowParser.parse_definition(sample_workflow_definition)
        assert result["name"] == "test_workflow"
        assert len(result["nodes"]) == 3

    def test_valid_with_approval(self, sample_workflow_with_approval: Dict[str, Any]) -> None:
        result = WorkflowParser.parse_definition(sample_workflow_with_approval)
        assert result["name"] == "approval_workflow"
        assert len(result["nodes"]) == 4

    def test_valid_with_condition(self, sample_workflow_with_condition: Dict[str, Any]) -> None:
        result = WorkflowParser.parse_definition(sample_workflow_with_condition)
        assert result["name"] == "conditional_workflow"
        assert len(result["nodes"]) == 5

    def test_valid_with_tool(self, sample_workflow_with_tool: Dict[str, Any]) -> None:
        result = WorkflowParser.parse_definition(sample_workflow_with_tool)
        assert result["name"] == "tool_workflow"
        assert len(result["nodes"]) == 3

    def test_missing_name_raises(self) -> None:
        with pytest.raises(WorkflowValidationError, match="'name' is required"):
            WorkflowParser.parse_definition({"nodes": []})

    def test_empty_name_raises(self) -> None:
        with pytest.raises(WorkflowValidationError, match="'name' is required"):
            WorkflowParser.parse_definition({"name": "", "nodes": []})

    def test_no_nodes_raises(self) -> None:
        with pytest.raises(WorkflowValidationError, match="'nodes' must be a list"):
            WorkflowParser.parse_definition({"name": "test"})

    def test_too_few_nodes_raises(self) -> None:
        with pytest.raises(WorkflowValidationError, match="'nodes' must be a list"):
            WorkflowParser.parse_definition(
                {"name": "test", "nodes": [{"type": "trigger", "name": "t"}]}
            )

    def test_missing_trigger_raises(self, invalid_workflow_no_trigger: Dict[str, Any]) -> None:
        with pytest.raises(WorkflowValidationError, match="must have a 'trigger' node"):
            WorkflowParser.parse_definition(invalid_workflow_no_trigger)

    def test_missing_end_raises(self, invalid_workflow_no_end: Dict[str, Any]) -> None:
        with pytest.raises(WorkflowValidationError, match="at least one 'end' node"):
            WorkflowParser.parse_definition(invalid_workflow_no_end)

    def test_duplicate_node_names_raises(self) -> None:
        with pytest.raises(WorkflowValidationError, match="Duplicate node name"):
            WorkflowParser.parse_definition(
                {
                    "name": "test",
                    "nodes": [
                        {"type": "trigger", "name": "start"},
                        {"type": "agent", "name": "start", "config": {"agent_name": "a"}},
                        {"type": "end", "name": "end"},
                    ],
                }
            )

    def test_invalid_node_type_raises(self) -> None:
        with pytest.raises(WorkflowValidationError, match="invalid type"):
            WorkflowParser.parse_definition(
                {
                    "name": "test",
                    "nodes": [
                        {"type": "trigger", "name": "start"},
                        {"type": "invalid_type", "name": "bad"},
                        {"type": "end", "name": "end"},
                    ],
                }
            )

    def test_missing_agent_name_raises(self) -> None:
        with pytest.raises(WorkflowValidationError, match="missing 'agent_name'"):
            WorkflowParser.parse_definition(
                {
                    "name": "test",
                    "nodes": [
                        {"type": "trigger", "name": "start"},
                        {"type": "agent", "name": "a", "config": {}},
                        {"type": "end", "name": "end"},
                    ],
                }
            )

    def test_missing_tool_name_raises(self) -> None:
        with pytest.raises(WorkflowValidationError, match="missing 'tool_name'"):
            WorkflowParser.parse_definition(
                {
                    "name": "test",
                    "nodes": [
                        {"type": "trigger", "name": "start"},
                        {"type": "tool", "name": "t", "config": {}},
                        {"type": "end", "name": "end"},
                    ],
                }
            )

    def test_missing_condition_expression_raises(self) -> None:
        with pytest.raises(WorkflowValidationError, match="missing 'expression'"):
            WorkflowParser.parse_definition(
                {
                    "name": "test",
                    "nodes": [
                        {"type": "trigger", "name": "start"},
                        {
                            "type": "condition",
                            "name": "c",
                            "config": {"true_next": "a", "false_next": "b"},
                        },
                        {"type": "end", "name": "a"},
                        {"type": "end", "name": "b"},
                    ],
                }
            )

    def test_missing_approvers_raises(self) -> None:
        with pytest.raises(WorkflowValidationError, match="missing 'approvers'"):
            WorkflowParser.parse_definition(
                {
                    "name": "test",
                    "nodes": [
                        {"type": "trigger", "name": "start"},
                        {"type": "approval", "name": "ap", "config": {}},
                        {"type": "end", "name": "end"},
                    ],
                }
            )

    def test_unknown_field_raises(self) -> None:
        with pytest.raises(WorkflowValidationError, match="unknown field"):
            WorkflowParser.parse_definition(
                {
                    "name": "test",
                    "nodes": [
                        {"type": "trigger", "name": "start"},
                        {
                            "type": "agent",
                            "name": "a",
                            "config": {"agent_name": "x"},
                            "unknown_field": True,
                        },
                        {"type": "end", "name": "end"},
                    ],
                }
            )

    def test_preserves_trigger_config(self, sample_workflow_definition: Dict[str, Any]) -> None:
        wf = dict(sample_workflow_definition)
        wf["trigger_type"] = "webhook"
        wf["trigger_config"] = {"secret": "abc123"}
        result = WorkflowParser.parse_definition(wf)
        assert result["trigger_type"] == "webhook"
        assert result["trigger_config"] == {"secret": "abc123"}

    def test_preserves_tags_timeout(self, sample_workflow_definition: Dict[str, Any]) -> None:
        wf = dict(sample_workflow_definition)
        wf["tags"] = ["devops", "test"]
        wf["timeout_seconds"] = 300
        result = WorkflowParser.parse_definition(wf)
        assert result["tags"] == ["devops", "test"]
        assert result["timeout_seconds"] == 300


class TestParseToNodes:
    """Tests for WorkflowParser.parse_to_nodes."""

    def test_returns_correct_node_types(self, sample_workflow_definition: Dict[str, Any]) -> None:
        parsed = WorkflowParser.parse_definition(sample_workflow_definition)
        node_map, start_node = WorkflowParser.parse_to_nodes(parsed)
        assert start_node == "start"
        assert len(node_map) == 3
        assert isinstance(node_map["start"], TriggerNode)
        assert isinstance(node_map["analysis"], AgentNode)
        assert isinstance(node_map["finish"], EndNode)

    def test_approval_node_type(self, sample_workflow_with_approval: Dict[str, Any]) -> None:
        parsed = WorkflowParser.parse_definition(sample_workflow_with_approval)
        node_map, start_node = WorkflowParser.parse_to_nodes(parsed)
        assert isinstance(node_map["review"], ApprovalNode)

    def test_condition_node_type(self, sample_workflow_with_condition: Dict[str, Any]) -> None:
        parsed = WorkflowParser.parse_definition(sample_workflow_with_condition)
        node_map, start_node = WorkflowParser.parse_to_nodes(parsed)
        assert isinstance(node_map["check_score"], ConditionNode)

    def test_tool_node_type(self, sample_workflow_with_tool: Dict[str, Any]) -> None:
        parsed = WorkflowParser.parse_definition(sample_workflow_with_tool)
        node_map, start_node = WorkflowParser.parse_to_nodes(parsed)
        assert isinstance(node_map["restart_pod"], ToolNode)

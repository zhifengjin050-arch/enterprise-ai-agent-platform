"""Workflow JSON DSL parser — Phase 9.

Validates and parses workflow definitions into executable node graphs.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from app.workflow_engine.models import NodeType
from app.workflow_engine.nodes import Node, NodeFactory

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# Validation errors
# ──────────────────────────────────────────────


class WorkflowValidationError(Exception):
    """Raised when a workflow definition is invalid."""


# ──────────────────────────────────────────────
# Parser
# ──────────────────────────────────────────────


class WorkflowParser:
    """Parses and validates JSON DSL workflow definitions."""

    REQUIRED_NODE_FIELDS = {"type", "name"}
    ALLOWED_NODE_FIELDS = {"type", "name", "config", "label", "next", "sort_order"}
    VALID_NODE_TYPES = {t.value for t in NodeType}

    @classmethod
    def parse_definition(cls, raw: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and normalize a raw JSON DSL definition.

        Args:
            raw: Parsed JSON dict from user input.

        Returns:
            Normalized definition dict.

        Raises:
            WorkflowValidationError: If the definition is invalid.
        """
        errors: List[str] = []

        # Top-level fields
        name = raw.get("name", "").strip()
        if not name:
            errors.append("'name' is required")

        nodes_raw = raw.get("nodes", [])
        if not isinstance(nodes_raw, list) or len(nodes_raw) < 2:
            errors.append("'nodes' must be a list with at least 2 entries")

        trigger: Optional[Dict[str, Any]] = None
        end: Optional[Dict[str, Any]] = None
        seen_names: set = set()
        node_index: Dict[str, Dict[str, Any]] = {}

        trigger_count = 0
        end_count = 0
        for i, node in enumerate(nodes_raw):
            node_errors = cls._validate_node(node, i, seen_names)
            errors.extend(node_errors)
            node_type = node.get("type", "")
            node_name = node.get("name", f"node_{i}")
            node_index[node_name] = node

            if node_type == "trigger":
                trigger_count += 1
                if trigger_count > 1:
                    errors.append(f"Multiple trigger nodes (index {i})")
                trigger = node
            elif node_type == "end":
                end_count += 1
                if end is None:
                    end = node

        if trigger_count == 0:
            errors.append("Workflow must have a 'trigger' node")
        if end_count == 0:
            errors.append("Workflow must have at least one 'end' node")

        # Validate connectivity — every node must be reachable
        # and every non-end node must have a 'next' or conditional routing
        if not errors:
            cls._validate_connectivity(nodes_raw, node_index, errors)

        # Validate node configs
        for i, node in enumerate(nodes_raw):
            cls._validate_node_config(node, i, errors)

        if errors:
            raise WorkflowValidationError(
                f"Workflow definition validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
            )

        return {
            "name": name,
            "description": raw.get("description", ""),
            "version": raw.get("version", "1.0"),
            "tags": raw.get("tags", []),
            "timeout_seconds": raw.get("timeout_seconds"),
            "max_retries": raw.get("max_retries", 0),
            "trigger_type": raw.get("trigger_type"),
            "trigger_config": raw.get("trigger_config"),
            "nodes": nodes_raw,
        }

    @classmethod
    def _validate_node(
        cls,
        node: Any,
        index: int,
        seen_names: set,
    ) -> List[str]:
        errors: List[str] = []

        if not isinstance(node, dict):
            errors.append(f"Node at index {index} must be a dict")
            return errors

        # Required fields
        for field in cls.REQUIRED_NODE_FIELDS:
            if field not in node:
                errors.append(f"Node at index {index} missing required field '{field}'")

        if "type" in node and "name" in node:
            node_type = node["type"]
            node_name = node["name"]

            if not isinstance(node_name, str) or not node_name.strip():
                errors.append(f"Node at index {index} has invalid 'name'")

            if node_name in seen_names:
                errors.append(f"Duplicate node name '{node_name}' at index {index}")
            seen_names.add(node_name)

            if node_type not in cls.VALID_NODE_TYPES:
                errors.append(
                    f"Node '{node_name}' has invalid type '{node_type}'. "
                    f"Allowed: {', '.join(cls.VALID_NODE_TYPES)}"
                )

        # Check for unknown fields
        for key in node:
            if key not in cls.ALLOWED_NODE_FIELDS:
                errors.append(f"Node at index {index} has unknown field '{key}'")

        return errors

    @classmethod
    def _validate_connectivity(
        cls,
        nodes: List[Dict[str, Any]],
        node_index: Dict[str, Dict[str, Any]],
        errors: List[str],
    ) -> None:
        """Basic connectivity validation — every node reachable from trigger."""
        # Build adjacency
        adjacency: Dict[str, List[str]] = {}
        for node in nodes:
            name = node.get("name", "")
            nxt = node.get("next")
            if isinstance(nxt, str):
                adjacency[name] = [nxt]
            elif isinstance(nxt, list):
                adjacency[name] = nxt
            else:
                adjacency[name] = []

        # BFS from trigger
        trigger_name = None
        for node in nodes:
            if node.get("type") == "trigger":
                trigger_name = node.get("name")
                break

        if trigger_name is None:
            return  # already reported

        visited = set()
        stack = [trigger_name]
        while stack:
            current = stack.pop()
            if current in visited:
                continue
            visited.add(current)
            for nxt in adjacency.get(current, []):
                if nxt not in node_index and nxt != "__end__":
                    errors.append(
                        f"Node '{current}' references unknown next node '{nxt}'"
                    )
                if nxt not in visited:
                    stack.append(nxt)

        unreachable = [n.get("name") for n in nodes if n.get("name") not in visited]
        if unreachable:
            errors.append(f"Unreachable nodes: {', '.join(unreachable)}")

    @classmethod
    def _validate_node_config(
        cls,
        node: Dict[str, Any],
        index: int,
        errors: List[str],
    ) -> None:
        """Validate type-specific node configuration."""
        node_type = node.get("type", "")
        node_name = node.get("name", f"node_{index}")
        config = node.get("config", {})

        if node_type == "agent":
            if not config.get("agent_name"):
                errors.append(
                    f"AgentNode '{node_name}' missing 'agent_name' in config"
                )
        elif node_type == "tool":
            if not config.get("tool_name"):
                errors.append(
                    f"ToolNode '{node_name}' missing 'tool_name' in config"
                )
        elif node_type == "condition":
            if not config.get("expression"):
                errors.append(
                    f"ConditionNode '{node_name}' missing 'expression' in config"
                )
            if not config.get("true_next"):
                errors.append(
                    f"ConditionNode '{node_name}' missing 'true_next' in config"
                )
            if not config.get("false_next"):
                errors.append(
                    f"ConditionNode '{node_name}' missing 'false_next' in config"
                )
        elif node_type == "approval":
            if not config.get("approvers"):
                errors.append(
                    f"ApprovalNode '{node_name}' missing 'approvers' in config"
                )
        elif node_type == "trigger":
            pass  # trigger has no mandatory config
        elif node_type == "end":
            pass  # end has no mandatory config

    @classmethod
    def parse_to_nodes(
        cls,
        definition: Dict[str, Any],
    ) -> Tuple[Dict[str, Node], str]:
        """Parse a validated definition into a node map.

        Args:
            definition: Parsed and validated definition dict (from parse_definition).

        Returns:
            (node_map, start_node_name) where node_map is {name: Node, ...}.
        """
        nodes = definition.get("nodes", [])
        node_map: Dict[str, Node] = {}
        start_node = ""

        for raw in nodes:
            node_type = raw.get("type", "")
            node_name = raw.get("name", "")
            config = raw.get("config", {})

            # Add edge routing info into config for condition nodes
            if node_type == "condition":
                config["true_next"] = raw.get("next", [{}])[0] if isinstance(raw.get("next"), list) else raw.get("true_next", "")
                config["false_next"] = raw.get("false_next", "")
            # For non-condition, add generic next
            if node_type != "condition":
                nxt = raw.get("next")
                if nxt:
                    config["next"] = nxt

            node = NodeFactory.create_node(
                node_type=node_type,
                node_name=node_name,
                config=config,
            )
            node_map[node_name] = node

            if node_type == "trigger":
                start_node = node_name

        return node_map, start_node

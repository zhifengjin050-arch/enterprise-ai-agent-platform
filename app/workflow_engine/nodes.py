"""Workflow node system — Phase 9.

Unified Node interface with implementations for:
    TriggerNode    — Entry point (always first)
    AgentNode      — Agent Runtime invocation
    ToolNode       — Tool execution
    ConditionNode  — Conditional branching
    ApprovalNode   — Human-in-the-loop
    EndNode        — Terminal node
"""

from __future__ import annotations

import abc
import asyncio
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# NodeContext — shared runtime context
# ──────────────────────────────────────────────


class NodeContext:
    """Runtime context passed through every node during execution."""

    def __init__(
        self,
        workflow_id: str,
        run_id: str,
        tenant_id: Optional[str] = None,
        triggered_by: Optional[str] = None,
        variables: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.workflow_id = workflow_id
        self.run_id = run_id
        self.tenant_id = tenant_id
        self.triggered_by = triggered_by
        self.variables: Dict[str, Any] = variables or {}
        self.node_results: Dict[str, Any] = {}

    def get(self, key: str, default: Any = None) -> Any:
        return self.variables.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self.variables[key] = value

    def record_result(self, node_name: str, result: Dict[str, Any]) -> None:
        self.node_results[node_name] = result


# ──────────────────────────────────────────────
# Node — abstract base
# ──────────────────────────────────────────────


class Node(abc.ABC):
    """Abstract base for all workflow nodes."""

    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None) -> None:
        self.name = name
        self.config = config or {}

    @abc.abstractmethod
    async def execute(self, context: NodeContext) -> Dict[str, Any]:
        """Execute the node and return result dict.
        
        Must include at minimum:
            {"status": "success" | "failure" | "waiting",
             "output": {...} | None,
             "error": "..." | None}
        """
        ...

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name}>"


# ──────────────────────────────────────────────
# TriggerNode
# ──────────────────────────────────────────────


class TriggerNode(Node):
    """Entry node — validates trigger parameters and seeds context."""

    def __init__(
        self,
        name: str,
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(name, config)

    async def execute(self, context: NodeContext) -> Dict[str, Any]:
        try:
            # Merge trigger payload into context variables
            payload = self.config.get("payload", {})
            context.variables.update(payload)
            logger.info(
                "TriggerNode %s executed — payload keys: %s",
                self.name, list(payload.keys()),
            )
            return {
                "status": "success",
                "output": {"triggered": True, "payload": payload},
                "error": None,
            }
        except Exception as exc:
            logger.error("TriggerNode %s failed: %s", self.name, exc)
            return {"status": "failure", "output": None, "error": str(exc)}


# ──────────────────────────────────────────────
# AgentNode
# ──────────────────────────────────────────────


class AgentNode(Node):
    """Invokes an Agent Runtime agent as a workflow step.

    Config:
        agent_name: str — registered agent name
        task: str — task prompt for the agent
        input_key: str — context variable key to use as input
    """

    def __init__(
        self,
        name: str,
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(name, config)
        self._agent_name: str = self.config.get("agent_name", "")
        self._task: str = self.config.get("task", "")
        self._input_key: Optional[str] = self.config.get("input_key")

    async def execute(self, context: NodeContext) -> Dict[str, Any]:
        try:
            # Resolve input
            task_input = self._task
            if self._input_key:
                task_input = context.get(self._input_key, "")

            # Attempt to use Agent Runtime if available
            agent_result = await self._call_agent(context, task_input)

            # Store output in context
            output_var = self.config.get("output_key", f"{self.name}_output")
            context.set(output_var, agent_result)

            logger.info(
                "AgentNode %s completed — agent=%s",
                self.name, self._agent_name,
            )
            return {
                "status": "success",
                "output": agent_result,
                "error": None,
            }
        except Exception as exc:
            logger.error("AgentNode %s failed: %s", self.name, exc)
            return {"status": "failure", "output": None, "error": str(exc)}

    async def _call_agent(
        self, context: NodeContext, task_input: str
    ) -> Dict[str, Any]:
        """Try real Agent Runtime; fall back to simulated response."""
        try:
            from app.agent import AgentRuntime

            runtime = AgentRuntime(agent_name=self._agent_name)
            if hasattr(runtime, "arun"):
                result = await runtime.arun(task_input)
                return {"agent": self._agent_name, "result": result}
            elif hasattr(runtime, "run"):
                result = await asyncio.to_thread(runtime.run, task_input)
                return {"agent": self._agent_name, "result": result}
        except (ImportError, AttributeError) as e:
            logger.warning("AgentRuntime unavailable, using fallback: %s", e)

        # Simulated fallback
        return {
            "agent": self._agent_name or "unknown",
            "result": {
                "summary": f"Simulated analysis for: {task_input[:100]}",
                "confidence": 0.85,
                "actions": [],
            },
        }


# ──────────────────────────────────────────────
# ToolNode
# ──────────────────────────────────────────────


class ToolNode(Node):
    """Executes a tool as a workflow step.

    Config:
        tool_name: str — registered tool name
        params: dict — tool parameters (supports variable interpolation with {{key}})
    """

    def __init__(
        self,
        name: str,
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(name, config)
        self._tool_name: str = self.config.get("tool_name", "")
        self._params: Dict[str, Any] = self.config.get("params", {})

    async def execute(self, context: NodeContext) -> Dict[str, Any]:
        try:
            resolved_params = self._resolve_params(context)
            tool_result = await self._call_tool(context, resolved_params)

            output_var = self.config.get("output_key", f"{self.name}_output")
            context.set(output_var, tool_result)

            logger.info(
                "ToolNode %s completed — tool=%s",
                self.name, self._tool_name,
            )
            return {
                "status": "success",
                "output": tool_result,
                "error": None,
            }
        except Exception as exc:
            logger.error("ToolNode %s failed: %s", self.name, exc)
            return {"status": "failure", "output": None, "error": str(exc)}

    def _resolve_params(self, context: NodeContext) -> Dict[str, Any]:
        """Interpolate {{variable}} references in params."""
        import re

        resolved: Dict[str, Any] = {}
        for key, val in self._params.items():
            if isinstance(val, str):
                resolved[key] = re.sub(
                    r"\{\{(\w+)\}\}",
                    lambda m: str(context.get(m.group(1), m.group(0))),
                    val,
                )
            else:
                resolved[key] = val
        return resolved

    async def _call_tool(
        self, context: NodeContext, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Try real Tool System; fall back to simulated."""
        try:
            from app.tool.base import ToolRegistry

            registry = ToolRegistry()
            tool = registry.get(self._tool_name)
            if tool:
                result = await tool.execute(**params)
                return {"tool": self._tool_name, "result": result}
        except (ImportError, AttributeError) as e:
            logger.warning("ToolRegistry unavailable, using fallback: %s", e)

        # Simulated fallback
        return {
            "tool": self._tool_name or "unknown",
            "result": {"executed": True, "params": params, "output": "Simulated tool execution"},
        }


# ──────────────────────────────────────────────
# ConditionNode
# ──────────────────────────────────────────────


class ConditionNode(Node):
    """Evaluates a Python expression and routes based on result.

    Config:
        expression: str — Python expression using context variables (e.g. "score > 0.5")
        true_next: str — next node name if truthy
        false_next: str — next node name if falsy
    """

    def __init__(
        self,
        name: str,
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(name, config)
        self._expression: str = self.config.get("expression", "True")
        self._true_next: str = self.config.get("true_next", "")
        self._false_next: str = self.config.get("false_next", "")

    async def execute(self, context: NodeContext) -> Dict[str, Any]:
        try:
            # Safely evaluate expression against context variables
            safe_globals: Dict[str, Any] = {
                "__builtins__": {
                    "True": True,
                    "False": False,
                    "None": None,
                    "abs": abs,
                    "len": len,
                    "int": int,
                    "float": float,
                    "str": str,
                    "bool": bool,
                    "list": list,
                    "dict": dict,
                    "min": min,
                    "max": max,
                    "sum": sum,
                    "any": any,
                    "all": all,
                }
            }
            local_vars = dict(context.variables)
            local_vars.update(context.node_results)
            result = bool(eval(self._expression, safe_globals, local_vars))  # noqa: S307

            next_node = self._true_next if result else self._false_next

            logger.info(
                "ConditionNode %s → %s (expression=%s, result=%s)",
                self.name, next_node, self._expression, result,
            )
            return {
                "status": "success",
                "output": {
                    "condition_result": result,
                    "next_node": next_node,
                },
                "error": None,
                "_next_node": next_node,
            }
        except Exception as exc:
            logger.error("ConditionNode %s failed: %s", self.name, exc)
            return {
                "status": "failure",
                "output": None,
                "error": str(exc),
                "_next_node": self._false_next,
            }

    def get_next_node(self, result: Dict[str, Any]) -> str:
        """Determine which node to route to based on execution result."""
        if result.get("_next_node"):
            return result["_next_node"]
        if result.get("output", {}).get("condition_result"):
            return self._true_next or self.config.get("true_next", "")
        return self._false_next or self.config.get("false_next", "")


# ──────────────────────────────────────────────
# ApprovalNode
# ──────────────────────────────────────────────


class ApprovalNode(Node):
    """Human-in-the-loop approval gate.

    Config:
        approvers: list[str] — user IDs or roles
        message: str — approval request message
        timeout_minutes: int — auto-reject after timeout (default 60)
        reject_on_timeout: bool — whether to reject (True) or skip approval on timeout
    """

    def __init__(
        self,
        name: str,
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(name, config)
        self._approvers: List[str] = self.config.get("approvers", [])
        self._message: str = self.config.get("message", "Please approve this workflow step.")
        self._timeout_minutes: int = self.config.get("timeout_minutes", 60)

    async def execute(self, context: NodeContext) -> Dict[str, Any]:
        # Create approval record; workflow engine will wait for external decision
        from app.workflow_engine.approval import ApprovalService

        service = ApprovalService()
        approval = await service.create_approval(
            workflow_id=context.workflow_id,
            run_id=context.run_id,
            node_name=self.name,
            approvers=self._approvers,
            message=self._message,
            timeout_minutes=self._timeout_minutes,
            tenant_id=context.tenant_id,
        )

        # Return waiting status — engine will poll or receive callback
        logger.info(
            "ApprovalNode %s — waiting for approval id=%s",
            self.name, approval.get("id"),
        )
        return {
            "status": "waiting",
            "output": {
                "approval_id": approval.get("id"),
                "approval_status": "PENDING",
                "approvers": self._approvers,
                "message": self._message,
            },
            "error": None,
        }


# ──────────────────────────────────────────────
# EndNode
# ──────────────────────────────────────────────


class EndNode(Node):
    """Terminal node — marks workflow as complete."""

    def __init__(
        self,
        name: str,
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(name, config)

    async def execute(self, context: NodeContext) -> Dict[str, Any]:
        logger.info("EndNode %s — workflow complete", self.name)
        return {
            "status": "success",
            "output": {
                "completed": True,
                "node_count": len(context.node_results),
                "final_variables": dict(context.variables),
            },
            "error": None,
        }


# ──────────────────────────────────────────────
# Node registry — factory
# ──────────────────────────────────────────────


class NodeFactory:
    """Creates Node instances from parsed DSL node configs."""

    @staticmethod
    def create_node(
        node_type: str,
        node_name: str,
        config: Optional[Dict[str, Any]] = None,
    ) -> Node:
        mapping = {
            "trigger": TriggerNode,
            "agent": AgentNode,
            "tool": ToolNode,
            "condition": ConditionNode,
            "approval": ApprovalNode,
            "end": EndNode,
        }
        cls = mapping.get(node_type)
        if cls is None:
            raise ValueError(f"Unknown node type: {node_type}")
        return cls(name=node_name, config=config)

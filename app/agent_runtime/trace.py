"""Agent observability trace."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List

from app.tenant.context import get_tenant_context


@dataclass
class AgentTrace:
    """In-memory trace for a single agent task execution."""

    task_id: str = ""
    agent: str = ""
    agent_type: str = ""
    tenant_id: str = ""
    user_id: str = ""
    model: str = ""
    tokens: int = 0
    latency_ms: int = 0
    tools: List[Dict[str, Any]] = field(default_factory=list)
    success: bool = False
    error: str = ""
    _started_at: float = 0.0

    def start(self, *, task_id: str, agent: str, agent_type: str = "") -> None:
        self.task_id = task_id
        self.agent = agent
        self.agent_type = agent_type
        ctx = get_tenant_context()
        if ctx:
            self.tenant_id = ctx.tenant_id or ""
            self.user_id = ctx.user_id or ""
        self._started_at = time.monotonic()
        self.tools = []

    def record_tool(self, name: str, *, latency_ms: int, success: bool) -> None:
        self.tools.append({
            "name": name,
            "latency_ms": latency_ms,
            "success": success,
        })

    def record_model(self, model: str, tokens: int = 0) -> None:
        self.model = model
        self.tokens = tokens

    def finish(self, *, success: bool, error: str = "") -> None:
        self.success = success
        self.error = error
        if self._started_at:
            self.latency_ms = int((time.monotonic() - self._started_at) * 1000)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "agent": self.agent,
            "agent_type": self.agent_type,
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "model": self.model,
            "tokens": self.tokens,
            "latency_ms": self.latency_ms,
            "tools": self.tools,
            "success": self.success,
            "error": self.error,
        }

"""Enterprise AI Agent Runtime.

Provides BaseAgent, TaskPlanner, Tool System, Memory, and Trace
without replacing the legacy ``app.agent.KnowledgeAgent``.
"""

from app.agent_runtime.agent import BaseAgent
from app.agent_runtime.context import ContextEngine
from app.agent_runtime.memory import AgentMemoryManager, agent_memory
from app.agent_runtime.models import (
    AgentRecord,
    AgentResult,
    AgentStatus,
    AgentTask,
    AgentTaskStatus,
    ExecutionPlan,
    PlanStep,
)
from app.agent_runtime.planner import TaskPlanner
from app.agent_runtime.trace import AgentTrace

__all__ = [
    "BaseAgent",
    "AgentRecord",
    "AgentResult",
    "AgentStatus",
    "AgentTask",
    "AgentTaskStatus",
    "ExecutionPlan",
    "PlanStep",
    "TaskPlanner",
    "AgentMemoryManager",
    "agent_memory",
    "AgentTrace",
    "ContextEngine",
]

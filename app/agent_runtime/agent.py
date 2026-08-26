"""BaseAgent — Enterprise Agent Runtime core."""

from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Dict, List, Optional

from app.agent_runtime.models import (
    AgentResult,
    AgentStatus,
    AgentTask,
    AgentTaskStatus,
    ExecutionPlan,
)
from app.agent_runtime.planner import TaskPlanner
from app.agent_runtime.tools.base import ToolContext
from app.agent_runtime.tools.registry import ToolRegistry, get_tool_registry
from app.agent_runtime.trace import AgentTrace
from app.core.exceptions import AgentExecutionException

logger = logging.getLogger(__name__)


class BaseAgent:
    """Enterprise agent with lifecycle management.

    Lifecycle: CREATED → INITIALIZED → RUNNING → (WAITING) → COMPLETED | FAILED

    Args:
        agent_type: Agent type key (e.g. knowledge).
        agent_id: Optional persistent agent ID.
        planner: Optional TaskPlanner.
        tools: Optional ToolRegistry.
        llm: Optional LLM gateway.
    """

    def __init__(
        self,
        *,
        agent_type: str = "knowledge",
        agent_id: Optional[str] = None,
        name: str = "EnterpriseAgent",
        planner: Optional[TaskPlanner] = None,
        tools: Optional[ToolRegistry] = None,
        llm: Any = None,
        tenant_id: Optional[str] = None,
    ) -> None:
        self.agent_type = agent_type
        self.agent_id = agent_id or str(uuid.uuid4())
        self.name = name
        self.tenant_id = tenant_id
        self._planner = planner or TaskPlanner()
        self._tools = tools or get_tool_registry()
        self._llm = llm
        self._status = AgentStatus.CREATED
        self._trace = AgentTrace()

    @property
    def status(self) -> AgentStatus:
        return self._status

    async def initialize(self) -> None:
        """Initialize agent resources."""
        if self._status not in (AgentStatus.CREATED, AgentStatus.FAILED):
            return
        if self._llm is None:
            try:
                from app.llm.gateway import get_llm_gateway

                self._llm = get_llm_gateway()
            except Exception:
                self._llm = None
        self._status = AgentStatus.INITIALIZED
        logger.info("Agent %s initialized (type=%s)", self.agent_id, self.agent_type)

    async def execute(
        self,
        input: Dict[str, Any],
        *,
        session: Any = None,
        task: Optional[AgentTask] = None,
    ) -> AgentResult:
        """Execute a full plan: plan → tools → synthesize answer.

        Args:
            input: Must contain ``query`` (or ``message``).
            session: Optional DB session for tools / persistence.
            task: Optional pre-created AgentTask row.

        Returns:
            AgentResult.
        """
        await self.initialize()
        self._status = AgentStatus.RUNNING
        query = str(input.get("query") or input.get("message") or "").strip()
        task_id = task.id if task is not None else str(uuid.uuid4())
        self._trace.start(task_id=task_id, agent=self.name, agent_type=self.agent_type)

        tool_calls: List[Dict[str, Any]] = []
        sources: List[Dict[str, Any]] = []
        plan: Optional[ExecutionPlan] = None

        try:
            if task is not None and session is not None:
                task.status = AgentTaskStatus.RUNNING.value
                await session.flush()

            plan = self._planner.plan(query)
            ctx = ToolContext(
                tenant_id=self.tenant_id,
                task_id=task_id,
                agent_id=self.agent_id,
                session=session,
            )

            for step in plan.steps:
                # Skip connector_sync without connector_id
                if step.tool == "connector_sync" and not step.input.get("connector_id"):
                    continue

                t0 = time.monotonic()
                result = await self._tools.execute(step.tool, step.input, ctx)
                latency = int((time.monotonic() - t0) * 1000)
                call_rec = {
                    "step": step.step,
                    "tool": step.tool,
                    "input": step.input,
                    "success": result.success,
                    "latency_ms": latency,
                    "error": result.error,
                }
                tool_calls.append(call_rec)
                self._trace.record_tool(step.tool, latency_ms=latency, success=result.success)

                if result.success and isinstance(result.data, list):
                    sources.extend([d for d in result.data if isinstance(d, dict)])
                elif result.success and isinstance(result.data, dict):
                    if "nodes" in result.data:
                        sources.append({"graph": result.data})
                    elif "document_id" in result.data or "id" in result.data:
                        sources.append(result.data)

            answer = await self._synthesize(query, sources, plan)

            self._status = AgentStatus.COMPLETED
            result_obj = AgentResult(
                success=True,
                answer=answer,
                sources=sources[:20],
                tool_calls=tool_calls,
                metadata={
                    "plan": plan.to_dict() if plan else {},
                    "trace": self._trace.to_dict(),
                },
                task_id=task_id,
            )

            if task is not None and session is not None:
                task.status = AgentTaskStatus.COMPLETED.value
                task.result_json = result_obj.to_dict()
                task.completed_at = datetime.now(timezone.utc)
                await session.flush()

            self._trace.finish(success=True)
            return result_obj

        except Exception as exc:
            self._status = AgentStatus.FAILED
            self._trace.finish(success=False, error=str(exc))
            logger.error("Agent %s failed: %s", self.agent_id, exc)
            if task is not None and session is not None:
                task.status = AgentTaskStatus.FAILED.value
                task.error = str(exc)
                task.completed_at = datetime.now(timezone.utc)
                await session.flush()
            raise AgentExecutionException(
                message=f"Agent execution failed: {exc}",
                details={"task_id": task_id, "error": str(exc)},
            ) from exc

    async def stream(
        self,
        input: Dict[str, Any],
        *,
        session: Any = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream execution events (thinking / tool_call / retrieval / answer)."""
        await self.initialize()
        self._status = AgentStatus.RUNNING
        query = str(input.get("query") or input.get("message") or "").strip()
        task_id = str(uuid.uuid4())

        yield {"type": "thinking", "content": "正在分析问题并制定执行计划…", "task_id": task_id}

        plan = self._planner.plan(query)
        yield {
            "type": "thinking",
            "content": f"计划: {plan.rationale}",
            "plan": plan.to_dict(),
            "task_id": task_id,
        }

        ctx = ToolContext(
            tenant_id=self.tenant_id,
            task_id=task_id,
            agent_id=self.agent_id,
            session=session,
        )
        sources: List[Dict[str, Any]] = []
        tool_calls: List[Dict[str, Any]] = []

        for step in plan.steps:
            if step.tool == "connector_sync" and not step.input.get("connector_id"):
                continue
            yield {
                "type": "tool_call",
                "name": step.tool,
                "step": step.step,
                "input": step.input,
                "task_id": task_id,
            }
            result = await self._tools.execute(step.tool, step.input, ctx)
            tool_calls.append(
                {
                    "tool": step.tool,
                    "success": result.success,
                    "error": result.error,
                }
            )
            if result.success:
                if step.tool == "knowledge_search":
                    yield {
                        "type": "retrieval",
                        "count": len(result.data) if isinstance(result.data, list) else 0,
                        "data": result.data if isinstance(result.data, list) else [],
                        "task_id": task_id,
                    }
                    if isinstance(result.data, list):
                        sources.extend([d for d in result.data if isinstance(d, dict)])
                elif isinstance(result.data, dict):
                    sources.append(result.data)

        answer = await self._synthesize(query, sources, plan)
        self._status = AgentStatus.COMPLETED
        yield {
            "type": "answer",
            "content": answer,
            "sources": sources[:10],
            "tool_calls": tool_calls,
            "task_id": task_id,
            "success": True,
        }

    async def cleanup(self) -> None:
        """Release resources."""
        self._status = AgentStatus.CREATED
        logger.info("Agent %s cleaned up", self.agent_id)

    async def _synthesize(
        self,
        query: str,
        sources: List[Dict[str, Any]],
        plan: Optional[ExecutionPlan],
    ) -> str:
        """Generate final answer from tool outputs via LLM or fallback."""
        snippets = []
        for s in sources[:8]:
            title = s.get("title") or s.get("name") or ""
            content = s.get("content") or s.get("snippet") or ""
            if not content and "nodes" in s:
                content = f"图谱节点数={len(s.get('nodes') or [])}"
            snippets.append(f"- {title}: {str(content)[:300]}")

        context_block = "\n".join(snippets) if snippets else "(无检索到相关资料)"

        if self._llm is not None:
            try:
                system = (
                    "你是企业知识助手。根据检索结果回答用户问题，"
                    "给出清晰、可执行的建议。若资料不足请明确说明。"
                )
                prompt = (
                    f"用户问题: {query}\n\n"
                    f"执行计划: {plan.rationale if plan else ''}\n\n"
                    f"检索资料:\n{context_block}\n\n"
                    "请用中文回答。"
                )
                answer = await self._llm.chat(prompt, system_prompt=system, temperature=0.3)
                self._trace.record_model(getattr(self._llm, "get_model_name", lambda: "llm")())
                return answer
            except Exception as exc:
                logger.warning("LLM synthesize failed: %s", exc)

        # Offline fallback
        if not snippets:
            return f"针对问题「{query}」，当前知识库未检索到足够资料。建议补充相关文档后重试。"
        return (
            f"针对问题「{query}」，基于检索到的 {len(sources)} 条资料：\n"
            f"{context_block}\n\n"
            "建议结合上述文档进一步排查（日志、资源配额、依赖服务）。"
        )

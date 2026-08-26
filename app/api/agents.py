"""Agent Runtime API — Enterprise AI Agent Platform endpoints.

Routes (prefix /api/agents):
    POST   /                 create agent
    GET    /                 list agents
    POST   /{id}/execute     execute task
    GET    /{id}/history     conversation / task history
    POST   /chat             SSE streaming chat
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import AliasChoices, BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent_runtime.agent import BaseAgent
from app.agent_runtime.memory import agent_memory
from app.agent_runtime.models import AgentMessage, AgentRecord, AgentTask, AgentTaskStatus
from app.audit.service import AuditEvent
from app.auth.dependencies import get_current_user, require_permission
from app.core.exceptions import AgentNotFoundException, InvalidParameter
from app.db.session import get_db
from app.quota.service import QuotaService
from app.tenant.context import get_tenant_id, get_user_id
from app.tenant.isolation import apply_tenant_filter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agents", tags=["Agent Runtime"])


# ── Request schemas ──


class CreateAgentRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    agent_type: str = "knowledge"
    config: Optional[Dict[str, Any]] = None
    tenant_id: Optional[str] = None


class ExecuteAgentRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    query: str = Field(
        ...,
        min_length=1,
        validation_alias=AliasChoices("query", "task"),
        description="Task text. `task` is accepted as a compatibility alias.",
    )
    input: Optional[Dict[str, Any]] = None
    conversation_id: Optional[str] = None


class ChatStreamRequest(BaseModel):
    query: str = Field(..., min_length=1)
    agent_id: Optional[str] = None
    conversation_id: Optional[str] = None
    tenant_id: Optional[str] = None


# ── Endpoints ──


@router.post("")
async def create_agent(
    body: CreateAgentRequest,
    session: AsyncSession = Depends(get_db),
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user),
    _=Depends(require_permission("agent.write")),
) -> Dict[str, Any]:
    """Create a registered agent record."""
    tenant_id = body.tenant_id
    if current_user and current_user.get("tenant_id"):
        tenant_id = tenant_id or current_user["tenant_id"]

    record = AgentRecord(
        name=body.name.strip(),
        agent_type=body.agent_type or "knowledge",
        config_json=body.config or {},
        tenant_id=tenant_id,
        enabled=True,
    )
    session.add(record)
    await session.flush()
    return {"success": True, "data": record.to_dict()}


@router.get("")
async def list_agents(
    tenant_id: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db),
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user),
    _=Depends(require_permission("agent.read")),
) -> Dict[str, Any]:
    """List registered agents (tenant-scoped when context present)."""
    tid = tenant_id or (current_user or {}).get("tenant_id") or get_tenant_id()
    stmt = select(AgentRecord).order_by(AgentRecord.created_at.desc())
    stmt = apply_tenant_filter(stmt, AgentRecord.tenant_id, tid)
    stmt = stmt.offset(offset).limit(limit)
    result = await session.execute(stmt)
    agents = [a.to_dict() for a in result.scalars().all()]
    return {"success": True, "data": agents, "total": len(agents)}


@router.post("/{agent_id}/execute")
async def execute_agent(
    agent_id: str,
    body: ExecuteAgentRequest,
    session: AsyncSession = Depends(get_db),
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user),
    _=Depends(require_permission("agent.execute")),
) -> Dict[str, Any]:
    """Execute a task on a registered agent."""
    record = await session.get(AgentRecord, agent_id)
    if record is None or not record.enabled:
        raise AgentNotFoundException(
            message=f"Agent '{agent_id}' not found",
            details={"agent_id": agent_id},
        )

    query = body.query.strip()
    if not query:
        raise InvalidParameter(message="query is required")

    tenant_id = record.tenant_id
    if current_user and current_user.get("tenant_id"):
        tenant_id = tenant_id or current_user["tenant_id"]
    tenant_id = tenant_id or get_tenant_id()
    user_id = (current_user or {}).get("id") or get_user_id()

    if tenant_id:
        await QuotaService(session).consume_agent_run(str(tenant_id))

    payload = {"query": query, **(body.input or {})}
    task = AgentTask(
        agent_id=record.id,
        agent_type=record.agent_type,
        tenant_id=tenant_id,
        user_id=user_id,
        input_json=payload,
        status=AgentTaskStatus.PENDING.value,
    )
    session.add(task)
    await session.flush()

    conversation_id = body.conversation_id or str(uuid.uuid4())
    agent_memory.add_user_message(conversation_id, query)

    agent = BaseAgent(
        agent_type=record.agent_type,
        agent_id=record.id,
        name=record.name,
        tenant_id=tenant_id,
    )
    result = await agent.execute(payload, session=session, task=task)
    agent_memory.add_assistant_message(conversation_id, result.answer)

    try:
        await agent_memory.persist_message(
            session,
            conversation_id=conversation_id,
            role="user",
            content=query,
            agent_id=record.id,
            task_id=task.id,
            tenant_id=tenant_id,
        )
        await agent_memory.persist_message(
            session,
            conversation_id=conversation_id,
            role="assistant",
            content=result.answer,
            agent_id=record.id,
            task_id=task.id,
            tenant_id=tenant_id,
            metadata={"sources_count": len(result.sources)},
        )
        await AuditEvent(session).record(
            "agent.execute",
            resource="agent",
            resource_id=record.id,
            tenant_id=tenant_id,
            user_id=user_id,
            details={"task_id": task.id, "success": result.success},
        )
    except Exception:
        logger.exception("Failed to persist agent memory or audit for task %s", task.id)

    await agent.cleanup()
    return {
        "success": True,
        "data": result.to_dict(),
        "conversation_id": conversation_id,
        "task_id": task.id,
    }


@router.get("/{agent_id}/history")
async def get_agent_history(
    agent_id: str,
    conversation_id: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    session: AsyncSession = Depends(get_db),
    _=Depends(require_permission("agent.read")),
) -> Dict[str, Any]:
    """Get task / message history for an agent."""
    record = await session.get(AgentRecord, agent_id)
    if record is None:
        raise AgentNotFoundException(
            message=f"Agent '{agent_id}' not found",
            details={"agent_id": agent_id},
        )

    # Tasks
    task_stmt = (
        select(AgentTask)
        .where(AgentTask.agent_id == agent_id)
        .order_by(AgentTask.created_at.desc())
        .limit(limit)
    )
    task_result = await session.execute(task_stmt)
    tasks = [t.to_dict() for t in task_result.scalars().all()]

    messages: List[Dict[str, Any]] = []
    if conversation_id:
        messages = await agent_memory.list_history(session, conversation_id, limit=limit)
    else:
        msg_stmt = (
            select(AgentMessage)
            .where(AgentMessage.agent_id == agent_id)
            .order_by(AgentMessage.created_at.desc())
            .limit(limit)
        )
        msg_result = await session.execute(msg_stmt)
        messages = [m.to_dict() for m in msg_result.scalars().all()]

    return {
        "success": True,
        "data": {
            "agent_id": agent_id,
            "tasks": tasks,
            "messages": messages,
        },
    }


@router.post("/chat")
async def agent_chat_stream(
    body: ChatStreamRequest,
    session: AsyncSession = Depends(get_db),
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user),
    _=Depends(require_permission("agent.execute")),
) -> StreamingResponse:
    """SSE streaming chat via Agent Runtime.

    Events: thinking | tool_call | retrieval | answer
    """
    query = body.query.strip()
    if not query:
        raise InvalidParameter(message="query is required")

    tenant_id = body.tenant_id
    if current_user and current_user.get("tenant_id"):
        tenant_id = tenant_id or current_user["tenant_id"]

    agent_id = body.agent_id
    agent_name = "EnterpriseAgent"
    agent_type = "knowledge"
    if agent_id:
        record = await session.get(AgentRecord, agent_id)
        if record is None:
            raise AgentNotFoundException(
                message=f"Agent '{agent_id}' not found",
                details={"agent_id": agent_id},
            )
        agent_name = record.name
        agent_type = record.agent_type
        tenant_id = tenant_id or record.tenant_id

    conversation_id = body.conversation_id or str(uuid.uuid4())
    agent_memory.add_user_message(conversation_id, query)

    agent = BaseAgent(
        agent_type=agent_type,
        agent_id=agent_id or str(uuid.uuid4()),
        name=agent_name,
        tenant_id=tenant_id,
    )

    async def event_generator():
        answer_text = ""
        async for event in agent.stream({"query": query}, session=session):
            if event.get("type") == "answer":
                answer_text = event.get("content") or ""
            payload = json.dumps(event, ensure_ascii=False)
            yield f"event: {event.get('type', 'message')}\ndata: {payload}\n\n"

        if answer_text:
            agent_memory.add_assistant_message(conversation_id, answer_text)
            try:
                await agent_memory.persist_message(
                    session,
                    conversation_id=conversation_id,
                    role="user",
                    content=query,
                    agent_id=agent_id,
                    tenant_id=tenant_id,
                )
                await agent_memory.persist_message(
                    session,
                    conversation_id=conversation_id,
                    role="assistant",
                    content=answer_text,
                    agent_id=agent_id,
                    tenant_id=tenant_id,
                )
                await session.commit()
            except Exception:
                pass

        done = json.dumps(
            {"type": "done", "conversation_id": conversation_id},
            ensure_ascii=False,
        )
        yield f"event: done\ndata: {done}\n\n"
        await agent.cleanup()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

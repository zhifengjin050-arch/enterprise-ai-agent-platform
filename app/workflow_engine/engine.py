"""Workflow Engine — Phase 9 Core.

Manages the full lifecycle of workflow definitions and executions:
    - create / get / update / delete workflow definitions
    - execute (start), pause, resume, cancel runs
    - node-by-node execution with persistence and error handling
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.session import get_session_factory
from app.workflow_engine.approval import ApprovalService
from app.workflow_engine.models import (
    ApprovalStatus,
    NodeType,
    TriggerType,
    WorkflowDefinition,
    WorkflowEvent,
    WorkflowExecution,
    WorkflowNode,
    WorkflowStatus,
)
from app.workflow_engine.nodes import ConditionNode, NodeContext
from app.workflow_engine.observability import (
    inc_workflow_exec_count,
    inc_workflow_node_count,
    observe_workflow_duration,
    record_workflow_trace,
)
from app.workflow_engine.observability import (
    log_workflow_event as obs_log_event,
)
from app.workflow_engine.parser import WorkflowParser
from app.workflow_engine.trigger import default_trigger_manager

logger = logging.getLogger(__name__)


class WorkflowEngine:
    """Central engine for enterprise workflow orchestration.

    Lifecycle:
        CREATED -> RUNNING -> (WAITING -> PAUSED)* -> RUNNING -> COMPLETED / FAILED
    """

    def __init__(self, session_factory=None) -> None:
        self._session_factory = session_factory or get_session_factory()
        self._active_runs: Dict[str, asyncio.Task] = {}
        self._paused_runs: Dict[str, Dict[str, Any]] = {}
        self._approval_service = ApprovalService()

    # ──────────────────────────────────────────────
    # Workflow Definition CRUD
    # ──────────────────────────────────────────────

    async def create_workflow(
        self,
        definition: Dict[str, Any],
        tenant_id: Optional[str] = None,
        created_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a new workflow definition from JSON DSL.

        Args:
            definition: Raw JSON DSL dict.
            tenant_id: Tenant isolation.
            created_by: Creator user ID.

        Returns:
            Created workflow definition dict.

        Raises:
            WorkflowValidationError: If definition is invalid.
        """
        # 1. Parse and validate
        parsed = WorkflowParser.parse_definition(definition)

        # 2. Persist
        workflow_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        db_def = WorkflowDefinition(
            id=workflow_id,
            name=parsed["name"],
            description=parsed.get("description", ""),
            version=parsed.get("version", "1.0"),
            definition=parsed,
            status=WorkflowStatus.CREATED,
            trigger_type=(
                TriggerType(parsed["trigger_type"]) if parsed.get("trigger_type") else None
            ),
            trigger_config=parsed.get("trigger_config"),
            timeout_seconds=parsed.get("timeout_seconds"),
            max_retries=parsed.get("max_retries", 0),
            tags=parsed.get("tags"),
            tenant_id=tenant_id,
            created_by=created_by,
            created_at=now,
            updated_at=now,
        )

        factory = self._session_factory
        async with factory() as session:
            session.add(db_def)

            # Persist nodes
            for i, raw_node in enumerate(parsed.get("nodes", [])):
                db_node = WorkflowNode(
                    id=str(uuid.uuid4()),
                    workflow_id=workflow_id,
                    node_type=NodeType(raw_node["type"]),
                    node_name=raw_node["name"],
                    label=raw_node.get("label"),
                    config=raw_node.get("config"),
                    next_nodes=(
                        raw_node["next"]
                        if isinstance(raw_node.get("next"), list)
                        else [raw_node["next"]] if raw_node.get("next") else None
                    ),
                    condition_expression=raw_node.get("config", {}).get("expression"),
                    timeout_seconds=raw_node.get("config", {}).get("timeout_seconds"),
                    retry_count=raw_node.get("config", {}).get("retry_count", 0),
                    sort_order=i,
                    tenant_id=tenant_id,
                    created_at=now,
                )
                session.add(db_node)

            await session.commit()

        logger.info(
            "Workflow created id=%s name=%s tenant=%s",
            workflow_id, parsed["name"], tenant_id,
        )

        return await self.get_workflow(workflow_id)

    async def get_workflow(
        self, workflow_id: str, tenant_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Get a workflow definition by ID."""
        factory = self._session_factory
        async with factory() as session:
            return await self._get_workflow_dict(session, workflow_id, tenant_id)

    async def get_workflows(
        self,
        tenant_id: Optional[str] = None,
        status: Optional[WorkflowStatus] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """List workflow definitions with optional filters."""
        factory = self._session_factory
        async with factory() as session:
            query = select(WorkflowDefinition).options(selectinload(WorkflowDefinition.nodes))

            if tenant_id:
                query = query.where(WorkflowDefinition.tenant_id == tenant_id)
            if status:
                query = query.where(WorkflowDefinition.status == status)

            query = query.order_by(WorkflowDefinition.created_at.desc())
            query = query.offset(offset).limit(limit)

            result = await session.execute(query)
            workflows = result.scalars().all()

            return [self._workflow_to_dict(w) for w in workflows]

    async def update_workflow(
        self,
        workflow_id: str,
        updates: Dict[str, Any],
        tenant_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Update a workflow definition."""
        factory = self._session_factory
        async with factory() as session:
            wf = await self._get_workflow(session, workflow_id, tenant_id)
            if wf is None:
                return None

            if "name" in updates:
                wf.name = updates["name"]
            if "description" in updates:
                wf.description = updates["description"]
            if "definition" in updates:
                parsed = WorkflowParser.parse_definition(updates["definition"])
                wf.definition = parsed
                # Rebuild nodes
                await self._rebuild_nodes(session, wf, parsed, tenant_id)
            if "status" in updates:
                wf.status = WorkflowStatus(updates["status"])

            wf.updated_at = datetime.now(timezone.utc)
            await session.commit()

            return self._workflow_to_dict(wf)

    async def delete_workflow(
        self, workflow_id: str, tenant_id: Optional[str] = None
    ) -> bool:
        """Delete a workflow definition."""
        factory = self._session_factory
        async with factory() as session:
            wf = await self._get_workflow(session, workflow_id, tenant_id)
            if wf is None:
                return False
            await session.delete(wf)
            await session.commit()
            logger.info("Workflow deleted id=%s", workflow_id)
            return True

    # ──────────────────────────────────────────────
    # Workflow Execution
    # ──────────────────────────────────────────────

    async def execute_workflow(
        self,
        workflow_id: str,
        trigger_type: str = "api",
        trigger_payload: Optional[Dict[str, Any]] = None,
        tenant_id: Optional[str] = None,
        triggered_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute a workflow — validate trigger, create run, and start execution.

        Args:
            workflow_id: Workflow definition ID.
            trigger_type: api | webhook | schedule | sync_event.
            trigger_payload: Trigger payload / context.
            tenant_id: Tenant isolation.
            triggered_by: User or system trigger source.

        Returns:
            Workflow run dict with initial status.
        """
        trigger_payload = trigger_payload or {}

        # 1. Get workflow definition
        factory = self._session_factory
        async with factory() as session:
            wf = await self._get_workflow(session, workflow_id, tenant_id)
            if wf is None:
                raise ValueError(f"Workflow {workflow_id} not found")
            if wf.status == WorkflowStatus.RUNNING:
                raise ValueError(f"Workflow {workflow_id} is already running")

            # 2. Validate trigger
            trigger_valid = await default_trigger_manager.validate_trigger(
                trigger_type, trigger_payload
            )
            if not trigger_valid:
                raise ValueError(
                    f"Trigger '{trigger_type}' validation failed for workflow {workflow_id}"
                )

            # 3. Extract context from trigger
            trigger_context = await default_trigger_manager.extract_context(
                trigger_type, trigger_payload
            )

            # 4. Create run record
            now = datetime.now(timezone.utc)
            run_id = str(uuid.uuid4())
            db_run = WorkflowExecution(
                id=run_id,
                workflow_id=workflow_id,
                workflow_name=wf.name,
                status=WorkflowStatus.RUNNING,
                trigger_type=TriggerType(trigger_type) if trigger_type else None,
                trigger_event_id=trigger_context.get("trigger_type"),
                context=trigger_context,
                started_at=now,
                tenant_id=tenant_id or wf.tenant_id,
                triggered_by=triggered_by,
                created_at=now,
                updated_at=now,
            )
            session.add(db_run)

            # 5. Update workflow status
            wf.status = WorkflowStatus.RUNNING
            wf.updated_at = now
            await session.commit()

            run_dict = self._run_to_dict(db_run)

        # 6. Start async execution
        task = asyncio.create_task(
            self._run_workflow_async(
                run_id=run_id,
                workflow_id=workflow_id,
                tenant_id=tenant_id or wf.tenant_id,
                triggered_by=triggered_by,
            )
        )
        self._active_runs[run_id] = task

        logger.info(
            "Workflow execution started id=%s run=%s trigger=%s",
            workflow_id, run_id, trigger_type,
        )

        # Observability
        act_tenant = tenant_id or wf.tenant_id
        record_workflow_trace(workflow_id, run_id, tenant_id=act_tenant, status="RUNNING")
        inc_workflow_exec_count(status="running", trigger_type=trigger_type, tenant_id=act_tenant)
        obs_log_event(workflow_id, run_id, event_type="workflow_started", data={"trigger_type": trigger_type}, tenant_id=act_tenant)

        return run_dict

    async def pause_workflow(
        self, run_id: str, tenant_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Pause a running or waiting workflow execution."""
        factory = self._session_factory
        async with factory() as session:
            run = await self._get_run(session, run_id, tenant_id)
            if run is None:
                return None
            if run.status not in (WorkflowStatus.RUNNING, WorkflowStatus.WAITING):
                raise ValueError(f"Run {run_id} is not RUNNING (status={run.status})")

            run.status = WorkflowStatus.PAUSED
            run.updated_at = datetime.now(timezone.utc)
            await session.commit()

            # Cancel the active task if running
            task = self._active_runs.pop(run_id, None)
            if task and not task.done():
                task.cancel()

            # Remove from active runs
            self._active_runs.pop(run_id, None)
            # Save paused state
            self._paused_runs[run_id] = {
                "workflow_id": run.workflow_id,
                "current_node": run.current_node,
                "context": run.context,
                "node_results": run.node_results,
            }

            # Record event
            await self._record_event(
                session, run.workflow_id, run_id,
                event_type="pause", tenant_id=tenant_id,
            )
            await session.commit()

        logger.info("Workflow run paused id=%s", run_id)
        return await self.get_run(run_id, tenant_id)

    async def resume_workflow(
        self, run_id: str, tenant_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Resume a paused workflow execution."""
        factory = self._session_factory
        async with factory() as session:
            run = await self._get_run(session, run_id, tenant_id)
            if run is None:
                return None
            if run.status not in (WorkflowStatus.PAUSED, WorkflowStatus.WAITING):
                raise ValueError(f"Run {run_id} is not PAUSED or WAITING (status={run.status})")

            run.status = WorkflowStatus.RUNNING
            run.updated_at = datetime.now(timezone.utc)
            await session.commit()

            # Record event
            await self._record_event(
                session, run.workflow_id, run_id,
                event_type="resume", tenant_id=tenant_id,
            )
            await session.commit()

        # Restart async execution from where it left off
        saved = self._paused_runs.pop(run_id, {})
        task = asyncio.create_task(
            self._run_workflow_async(
                run_id=run_id,
                workflow_id=saved.get("workflow_id", run.workflow_id),
                tenant_id=tenant_id,
                triggered_by=saved.get("context", {}).get("triggered_by"),
                resume_from_node=saved.get("current_node"),
            )
        )
        self._active_runs[run_id] = task

        logger.info("Workflow run resumed id=%s", run_id)
        return await self.get_run(run_id, tenant_id)

    async def cancel_workflow(
        self, run_id: str, tenant_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Cancel a running or paused workflow execution."""
        factory = self._session_factory
        async with factory() as session:
            run = await self._get_run(session, run_id, tenant_id)
            if run is None:
                return None
            if run.status not in (WorkflowStatus.RUNNING, WorkflowStatus.PAUSED, WorkflowStatus.WAITING):
                raise ValueError(
                    f"Run {run_id} cannot be cancelled (status={run.status})"
                )

            run.status = WorkflowStatus.FAILED
            run.error = "Cancelled by user"
            run.completed_at = datetime.now(timezone.utc)
            run.duration_ms = self._compute_duration_ms(run.started_at, run.completed_at)
            run.updated_at = datetime.now(timezone.utc)
            await session.commit()

            # Remove from paused state
            self._paused_runs.pop(run_id, None)
            # Cancel active task
            task = self._active_runs.pop(run_id, None)
            if task and not task.done():
                task.cancel()
            self._paused_runs.pop(run_id, None)
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass

            # Record event
            await self._record_event(
                session, run.workflow_id, run_id,
                event_type="cancel", event_data={"reason": "cancelled_by_user"},
                tenant_id=tenant_id,
            )
            await session.commit()

        logger.info("Workflow run cancelled id=%s", run_id)
        return await self.get_run(run_id, tenant_id)

    # ──────────────────────────────────────────────
    # Run Query
    # ──────────────────────────────────────────────

    async def get_run(
        self, run_id: str, tenant_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Get a workflow run by ID."""
        factory = self._session_factory
        async with factory() as session:
            run = await self._get_run(session, run_id, tenant_id)
            return self._run_to_dict(run) if run else None

    async def get_runs(
        self,
        workflow_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        status: Optional[WorkflowStatus] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """List workflow runs with optional filters."""
        factory = self._session_factory
        async with factory() as session:
            query = select(WorkflowExecution)

            if tenant_id:
                query = query.where(WorkflowExecution.tenant_id == tenant_id)
            if workflow_id:
                query = query.where(WorkflowExecution.workflow_id == workflow_id)
            if status:
                query = query.where(WorkflowExecution.status == status)

            query = query.order_by(WorkflowExecution.created_at.desc())
            query = query.offset(offset).limit(limit)

            result = await session.execute(query)
            runs = result.scalars().all()
            return [self._run_to_dict(r) for r in runs]

    async def get_run_events(
        self,
        run_id: str,
        tenant_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Get events for a specific run."""
        factory = self._session_factory
        async with factory() as session:
            query = (
                select(WorkflowEvent)
                .where(WorkflowEvent.run_id == run_id)
                .order_by(WorkflowEvent.created_at.asc())
                .limit(limit)
            )
            result = await session.execute(query)
            events = result.scalars().all()
            return [self._event_to_dict(e) for e in events]

    # ──────────────────────────────────────────────
    # Internal: Async execution
    # ──────────────────────────────────────────────

    async def _run_workflow_async(
        self,
        run_id: str,
        workflow_id: str,
        tenant_id: Optional[str] = None,
        triggered_by: Optional[str] = None,
        resume_from_node: Optional[str] = None,
    ) -> None:
        """Execute workflow nodes sequentially (async internal)."""
        try:
            # Load nodes from workflow definition
            factory = self._session_factory
            async with factory() as session:
                wf = await self._get_workflow(session, workflow_id, tenant_id)
                if wf is None:
                    raise ValueError(f"Workflow {workflow_id} not found")

                node_map, start_node = WorkflowParser.parse_to_nodes(wf.definition)

            # Build execution order from trigger
            current_node_name = resume_from_node or start_node

            # Build context
            run = await self.get_run(run_id, tenant_id)
            context = NodeContext(
                workflow_id=workflow_id,
                run_id=run_id,
                tenant_id=tenant_id,
                triggered_by=triggered_by,
                variables=run.get("context", {}).get("payload", {}) if run else {},
            )

            # Load saved results if resuming
            if resume_from_node and run:
                saved_results = run.get("node_results", {}) or {}
                context.node_results = saved_results

            visited: set = set()
            max_steps = 100  # Safety limit

            for _ in range(max_steps):
                if current_node_name is None or current_node_name == "__end__":
                    break

                node = node_map.get(current_node_name)
                if node is None:
                    raise ValueError(f"Node '{current_node_name}' not found in workflow")

                # Check for pause/cancel signal
                if run_id in self._paused_runs:
                    break

                # Check pause state
                run_status = await self._check_run_status(run_id, tenant_id)
                if run_status == WorkflowStatus.PAUSED.value:
                    break
                if run_status in (WorkflowStatus.FAILED.value, WorkflowStatus.COMPLETED.value):
                    break

                # Observability: node start
                inc_workflow_node_count(node_type=node.__class__.__name__.replace("Node", "").lower() or "unknown", tenant_id=tenant_id)
                record_workflow_trace(workflow_id, run_id, node_name=current_node_name, tenant_id=tenant_id, status="RUNNING")

                # Execute node
                await self._record_node_event(
                    run_id, workflow_id, current_node_name, "node_start", tenant_id,
                )

                # Record node start in run
                async with factory() as session:
                    await self._update_run_current_node(
                        session, run_id, current_node_name, tenant_id,
                    )

                result = await node.execute(context)

                # Record node result
                context.record_result(current_node_name, result)

                # Observability: node end
                node_status = result.get("status", "unknown")
                record_workflow_trace(workflow_id, run_id, node_name=current_node_name, tenant_id=tenant_id, status=node_status.upper())
                if node_status == "failure":
                    inc_workflow_node_count(node_type=node.__class__.__name__.replace("Node", "").lower(), status="failure", tenant_id=tenant_id)
                elif node_status == "waiting":
                    inc_workflow_node_count(node_type=node.__class__.__name__.replace("Node", "").lower(), status="waiting", tenant_id=tenant_id)

                await self._record_node_event(
                    run_id, workflow_id, current_node_name, "node_end",
                    tenant_id, event_data={"result_status": node_status},
                )

                # Handle result status
                if result.get("status") == "failure":
                    async with factory() as session:
                        await self._fail_run(
                            session, run_id, result.get("error", "Node execution failed"),
                            tenant_id,
                        )
                    return

                if result.get("status") == "waiting":
                    # Approval or external input needed
                    async with factory() as session:
                        run_db = await self._get_run(session, run_id, tenant_id)
                        if run_db:
                            run_db.status = WorkflowStatus.WAITING
                            run_db.node_results = context.node_results
                            run_db.context = context.variables if hasattr(context, 'variables') else {}
                            run_db.updated_at = datetime.now(timezone.utc)
                            await session.commit()

                    # If it was an approval, register callback
                    if isinstance(node, ConditionNode):
                        pass
                    else:
                        approval_id = result.get("output", {}).get("approval_id")
                        if approval_id and hasattr(self, '_approval_service'):
                            async def approval_callback(
                                approval_data: Dict[str, Any],
                                rid: str = run_id,
                                wid: str = workflow_id,
                                tid: Optional[str] = tenant_id,
                                cnn: str = current_node_name,
                            ) -> None:
                                await self._handle_approval_callback(
                                    approval_data, rid, wid, tid, cnn,
                                )
                            self._approval_service.register_callback(
                                approval_id, approval_callback,
                            )
                    return

                # Determine next node
                if isinstance(node, ConditionNode):
                    current_node_name = node.get_next_node(result)
                else:
                    nxt = node.config.get("next")
                    if isinstance(nxt, list):
                        current_node_name = nxt[0] if nxt else None
                    elif isinstance(nxt, str):
                        current_node_name = nxt
                    else:
                        current_node_name = None

                if current_node_name in visited:
                    logger.warning(
                        "Cycle detected at node '%s' in run %s — breaking",
                        current_node_name, run_id,
                    )
                    break
                visited.add(current_node_name)

            # Mark as completed
            async with factory() as session:
                now = datetime.now(timezone.utc)
                run_db = await self._get_run(session, run_id, tenant_id)
                if run_db and run_db.status == WorkflowStatus.RUNNING:
                    run_db.status = WorkflowStatus.COMPLETED
                    run_db.completed_at = now
                    run_db.duration_ms = self._compute_duration_ms(run_db.started_at, now)
                    run_db.node_results = context.node_results
                    run_db.context = context.variables if hasattr(context, 'variables') else {}
                    run_db.updated_at = now
                    await session.commit()

                    # Observability: workflow completed
                    dur = run_db.duration_ms or 0
                    record_workflow_trace(workflow_id, run_id, tenant_id=tenant_id, status="COMPLETED", duration_ms=dur)
                    inc_workflow_exec_count(status="completed", tenant_id=tenant_id)
                    observe_workflow_duration(seconds=dur / 1000.0, workflow_id=workflow_id, status="completed")
                    obs_log_event(workflow_id, run_id, event_type="workflow_completed", tenant_id=tenant_id)

                    # Update workflow definition status
                    wf_db = await self._get_workflow(session, workflow_id, tenant_id)
                    if wf_db:
                        wf_db.status = WorkflowStatus.COMPLETED
                        wf_db.updated_at = now
                        await session.commit()

        except asyncio.CancelledError:
            logger.info("Workflow run %s was cancelled", run_id)
        except Exception as exc:
            logger.error("Workflow run %s failed: %s", run_id, exc)
            factory = self._session_factory
            async with factory() as session:
                await self._fail_run(session, run_id, str(exc), tenant_id)
                # Observability: workflow failed
                record_workflow_trace(workflow_id, run_id, tenant_id=tenant_id, status="FAILED", error=str(exc))
                inc_workflow_exec_count(status="failed", tenant_id=tenant_id)
                obs_log_event(workflow_id, run_id, event_type="workflow_failed", data={"error": str(exc)}, tenant_id=tenant_id)
        finally:
            self._active_runs.pop(run_id, None)

    async def _handle_approval_callback(
        self,
        approval_data: Dict[str, Any],
        run_id: str,
        workflow_id: str,
        tenant_id: Optional[str],
        current_node_name: str,
    ) -> None:
        """Handle approval decision: resume or fail the workflow."""
        status = approval_data.get("status", "")
        factory = self._session_factory

        async with factory() as session:
            run = await self._get_run(session, run_id, tenant_id)
            if run is None or run.status != WorkflowStatus.WAITING:
                return

            if status == ApprovalStatus.APPROVED.value:
                run.status = WorkflowStatus.RUNNING
                await self._record_event(
                    session, workflow_id, run_id,
                    event_type="approval",
                    event_data={"decision": "approved", "approval_id": approval_data.get("id")},
                    tenant_id=tenant_id,
                )
                await session.commit()

                # Resume execution
                task = asyncio.create_task(
                    self._run_workflow_async(
                        run_id=run_id,
                        workflow_id=workflow_id,
                        tenant_id=tenant_id,
                        resume_from_node=current_node_name,
                    )
                )
                self._active_runs[run_id] = task

            elif status in (ApprovalStatus.REJECTED.value, ApprovalStatus.TIMEOUT.value):
                run.status = WorkflowStatus.FAILED
                run.error = f"Approval {status.lower()}: {approval_data.get('comment', '')}"
                run.completed_at = datetime.now(timezone.utc)
                run.duration_ms = self._compute_duration_ms(run.started_at, run.completed_at)
                await self._record_event(
                    session, workflow_id, run_id,
                    event_type="approval",
                    event_data={"decision": status.lower(), "approval_id": approval_data.get("id")},
                    tenant_id=tenant_id,
                )
                await session.commit()

    # ──────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────

    @staticmethod
    def _compute_duration_ms(started_at: Optional[datetime], completed_at: Optional[datetime]) -> Optional[float]:
        """Compute duration in ms from two datetimes, handling timezone-naive/aware mismatch."""
        if started_at is None or completed_at is None:
            return None
        # Ensure both are timezone-aware (SQLite may return naive datetimes)
        if started_at.tzinfo is None:
            started_at = started_at.replace(tzinfo=timezone.utc)
        if completed_at.tzinfo is None:
            completed_at = completed_at.replace(tzinfo=timezone.utc)
        return (completed_at - started_at).total_seconds() * 1000

    async def _get_workflow(
        self,
        session: AsyncSession,
        workflow_id: str,
        tenant_id: Optional[str] = None,
    ) -> Optional[WorkflowDefinition]:
        query = (
            select(WorkflowDefinition)
            .options(selectinload(WorkflowDefinition.nodes))
            .where(WorkflowDefinition.id == workflow_id)
        )
        if tenant_id:
            query = query.where(WorkflowDefinition.tenant_id == tenant_id)
        result = await session.execute(query)
        return result.scalar_one_or_none()

    async def _get_workflow_dict(
        self,
        session: AsyncSession,
        workflow_id: str,
        tenant_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        wf = await self._get_workflow(session, workflow_id, tenant_id)
        return self._workflow_to_dict(wf) if wf else None

    async def _get_run(
        self,
        session: AsyncSession,
        run_id: str,
        tenant_id: Optional[str] = None,
    ) -> Optional[WorkflowExecution]:
        query = select(WorkflowExecution).where(WorkflowExecution.id == run_id)
        if tenant_id:
            query = query.where(WorkflowExecution.tenant_id == tenant_id)
        result = await session.execute(query)
        return result.scalar_one_or_none()

    async def _check_run_status(
        self, run_id: str, tenant_id: Optional[str] = None
    ) -> Optional[str]:
        factory = self._session_factory
        async with factory() as session:
            run = await self._get_run(session, run_id, tenant_id)
            return run.status.value if run else None

    async def _update_run_current_node(
        self,
        session: AsyncSession,
        run_id: str,
        node_name: str,
        tenant_id: Optional[str] = None,
    ) -> None:
        run = await self._get_run(session, run_id, tenant_id)
        if run:
            run.current_node = node_name
            run.updated_at = datetime.now(timezone.utc)
            await session.commit()

    async def _fail_run(
        self,
        session: AsyncSession,
        run_id: str,
        error: str,
        tenant_id: Optional[str] = None,
    ) -> None:
        run = await self._get_run(session, run_id, tenant_id)
        if run:
            run.status = WorkflowStatus.FAILED
            run.error = error
            run.completed_at = datetime.now(timezone.utc)
            run.duration_ms = self._compute_duration_ms(run.started_at, run.completed_at)
            run.updated_at = datetime.now(timezone.utc)
            await session.commit()

            # Also update workflow status
            wf = await self._get_workflow(session, run.workflow_id, tenant_id)
            if wf:
                wf.status = WorkflowStatus.FAILED
                wf.updated_at = datetime.now(timezone.utc)
                await session.commit()

    async def _record_event(
        self,
        session: AsyncSession,
        workflow_id: str,
        run_id: str,
        event_type: str,
        node_name: Optional[str] = None,
        event_data: Optional[Dict[str, Any]] = None,
        severity: str = "info",
        tenant_id: Optional[str] = None,
        created_by: Optional[str] = None,
    ) -> WorkflowEvent:
        event = WorkflowEvent(
            id=str(uuid.uuid4()),
            workflow_id=workflow_id,
            run_id=run_id,
            node_name=node_name,
            event_type=event_type,
            event_data=event_data,
            severity=severity,
            tenant_id=tenant_id,
            created_by=created_by,
        )
        session.add(event)
        return event

    async def _record_node_event(
        self,
        run_id: str,
        workflow_id: str,
        node_name: str,
        event_type: str,
        tenant_id: Optional[str] = None,
        event_data: Optional[Dict[str, Any]] = None,
    ) -> None:
        factory = self._session_factory
        async with factory() as session:
            await self._record_event(
                session, workflow_id, run_id, event_type,
                node_name=node_name, event_data=event_data,
                tenant_id=tenant_id,
            )
            await session.commit()

    async def _rebuild_nodes(
        self,
        session: AsyncSession,
        wf: WorkflowDefinition,
        parsed: Dict[str, Any],
        tenant_id: Optional[str] = None,
    ) -> None:
        """Delete and recreate nodes when definition is updated."""
        # Delete existing
        existing_nodes = await session.execute(
            select(WorkflowNode).where(WorkflowNode.workflow_id == wf.id)
        )
        for node in existing_nodes.scalars().all():
            await session.delete(node)

        # Create new
        now = datetime.now(timezone.utc)
        for i, raw_node in enumerate(parsed.get("nodes", [])):
            db_node = WorkflowNode(
                id=str(uuid.uuid4()),
                workflow_id=wf.id,
                node_type=NodeType(raw_node["type"]),
                node_name=raw_node["name"],
                label=raw_node.get("label"),
                config=raw_node.get("config"),
                next_nodes=(
                    raw_node["next"]
                    if isinstance(raw_node.get("next"), list)
                    else [raw_node["next"]] if raw_node.get("next") else None
                ),
                sort_order=i,
                tenant_id=tenant_id,
                created_at=now,
            )
            session.add(db_node)

    # ──────────────────────────────────────────────
    # Serialization
    # ──────────────────────────────────────────────

    @staticmethod
    def _workflow_to_dict(wf: WorkflowDefinition) -> Dict[str, Any]:
        return {
            "id": wf.id,
            "name": wf.name,
            "description": wf.description,
            "version": wf.version,
            "definition": wf.definition,
            "status": wf.status.value if wf.status else None,
            "trigger_type": wf.trigger_type.value if wf.trigger_type else None,
            "trigger_config": wf.trigger_config,
            "timeout_seconds": wf.timeout_seconds,
            "max_retries": wf.max_retries,
            "tags": wf.tags,
            "tenant_id": wf.tenant_id,
            "created_by": wf.created_by,
            "created_at": wf.created_at.isoformat() if wf.created_at else None,
            "updated_at": wf.updated_at.isoformat() if wf.updated_at else None,
            "node_count": len(wf.nodes) if wf.nodes else 0,
        }

    @staticmethod
    def _run_to_dict(run: WorkflowExecution) -> Dict[str, Any]:
        return {
            "id": run.id,
            "workflow_id": run.workflow_id,
            "workflow_name": run.workflow_name,
            "status": run.status.value if run.status else None,
            "trigger_type": run.trigger_type.value if run.trigger_type else None,
            "trigger_event_id": run.trigger_event_id,
            "current_node": run.current_node,
            "node_results": run.node_results,
            "context": run.context,
            "error": run.error,
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
            "duration_ms": run.duration_ms,
            "retry_count": run.retry_count,
            "tenant_id": run.tenant_id,
            "triggered_by": run.triggered_by,
            "created_at": run.created_at.isoformat() if run.created_at else None,
            "updated_at": run.updated_at.isoformat() if run.updated_at else None,
        }

    @staticmethod
    def _event_to_dict(event: WorkflowEvent) -> Dict[str, Any]:
        return {
            "id": event.id,
            "workflow_id": event.workflow_id,
            "run_id": event.run_id,
            "node_name": event.node_name,
            "event_type": event.event_type,
            "event_data": event.event_data,
            "severity": event.severity,
            "tenant_id": event.tenant_id,
            "created_by": event.created_by,
            "created_at": event.created_at.isoformat() if event.created_at else None,
        }


# Module-level singleton
workflow_engine = WorkflowEngine()

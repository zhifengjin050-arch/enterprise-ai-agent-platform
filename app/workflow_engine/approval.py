"""Approval service — Phase 9.

Human-in-the-loop approval for production releases,
database modifications, auto-fix confirmations, etc.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Awaitable, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class ApprovalRecord:
    """In-memory approval record.

    In production, this would be persisted to the workflow_events table
    and/or a dedicated approvals table. For Phase 9 we keep it light.
    """

    def __init__(
        self,
        approval_id: str,
        workflow_id: str,
        run_id: str,
        node_name: str,
        approvers: List[str],
        message: str,
        status: str = "PENDING",
        timeout_minutes: int = 60,
        tenant_id: Optional[str] = None,
        created_by: Optional[str] = None,
    ) -> None:
        self.id = approval_id
        self.workflow_id = workflow_id
        self.run_id = run_id
        self.node_name = node_name
        self.approvers = approvers
        self.message = message
        self.status = status
        self.timeout_minutes = timeout_minutes
        self.comment: Optional[str] = None
        self.decided_by: Optional[str] = None
        self.tenant_id = tenant_id
        self.created_by = created_by
        self.created_at = datetime.now(timezone.utc)
        self.decided_at: Optional[datetime] = None

    def is_expired(self) -> bool:
        if self.status != "PENDING":
            return False
        elapsed = datetime.now(timezone.utc) - self.created_at
        return elapsed >= timedelta(minutes=self.timeout_minutes)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "workflow_id": self.workflow_id,
            "run_id": self.run_id,
            "node_name": self.node_name,
            "approvers": self.approvers,
            "message": self.message,
            "status": self.status,
            "timeout_minutes": self.timeout_minutes,
            "comment": self.comment,
            "decided_by": self.decided_by,
            "tenant_id": self.tenant_id,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "decided_at": self.decided_at.isoformat() if self.decided_at else None,
        }


class ApprovalService:
    """Manages human approval workflow.

    Features:
        - Create approval requests
        - Approve / reject
        - Automatic timeout handling
        - Callback to running workflow engine
    """

    def __init__(self) -> None:
        self._approvals: Dict[str, ApprovalRecord] = {}
        self._callbacks: Dict[str, List[Callable]] = {}
        self._timeout_task: Optional[asyncio.Task] = None
        self._running = False

    async def start(self) -> None:
        """Start the timeout checker loop."""
        if self._running:
            return
        self._running = True
        self._timeout_task = asyncio.create_task(self._timeout_loop())
        logger.info("ApprovalService started")

    async def stop(self) -> None:
        """Stop the timeout checker loop."""
        self._running = False
        if self._timeout_task:
            self._timeout_task.cancel()
            self._timeout_task = None
        logger.info("ApprovalService stopped")

    async def create_approval(
        self,
        workflow_id: str,
        run_id: str,
        node_name: str,
        approvers: List[str],
        message: str,
        timeout_minutes: int = 60,
        tenant_id: Optional[str] = None,
        created_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a new pending approval.

        Args:
            workflow_id: The workflow definition ID.
            run_id: The current workflow run ID.
            node_name: The approval node name.
            approvers: List of user IDs or roles who can approve.
            message: Human-readable approval request message.
            timeout_minutes: Minutes before auto-expiry.
            tenant_id: Tenant isolation.
            created_by: User or system that created the request.

        Returns:
            Approval record dict.
        """
        approval_id = str(uuid.uuid4())
        record = ApprovalRecord(
            approval_id=approval_id,
            workflow_id=workflow_id,
            run_id=run_id,
            node_name=node_name,
            approvers=approvers,
            message=message,
            status="PENDING",
            timeout_minutes=timeout_minutes,
            tenant_id=tenant_id,
            created_by=created_by,
        )
        self._approvals[approval_id] = record
        logger.info(
            "Approval created id=%s workflow=%s run=%s node=%s",
            approval_id,
            workflow_id,
            run_id,
            node_name,
        )
        return record.to_dict()

    async def approve(
        self,
        approval_id: str,
        user_id: str,
        comment: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Approve a pending request.

        Args:
            approval_id: The approval record ID.
            user_id: The user who approved.
            comment: Optional approval comment.

        Returns:
            Updated approval record.

        Raises:
            ValueError: If approval not found or not pending.
        """
        record = self._approvals.get(approval_id)
        if record is None:
            raise ValueError(f"Approval {approval_id} not found")
        if record.status != "PENDING":
            raise ValueError(f"Approval {approval_id} is not pending (status={record.status})")

        record.status = "APPROVED"
        record.decided_by = user_id
        record.comment = comment
        record.decided_at = datetime.now(timezone.utc)

        logger.info(
            "Approval %s approved by %s",
            approval_id,
            user_id,
        )
        await self._fire_callback(approval_id, record.to_dict())
        return record.to_dict()

    async def reject(
        self,
        approval_id: str,
        user_id: str,
        comment: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Reject a pending request.

        Args:
            approval_id: The approval record ID.
            user_id: The user who rejected.
            comment: Optional rejection reason.

        Returns:
            Updated approval record.

        Raises:
            ValueError: If approval not found or not pending.
        """
        record = self._approvals.get(approval_id)
        if record is None:
            raise ValueError(f"Approval {approval_id} not found")
        if record.status != "PENDING":
            raise ValueError(f"Approval {approval_id} is not pending (status={record.status})")

        record.status = "REJECTED"
        record.decided_by = user_id
        record.comment = comment
        record.decided_at = datetime.now(timezone.utc)

        logger.info(
            "Approval %s rejected by %s",
            approval_id,
            user_id,
        )
        await self._fire_callback(approval_id, record.to_dict())
        return record.to_dict()

    async def get_approval(self, approval_id: str) -> Optional[Dict[str, Any]]:
        """Get an approval record by ID."""
        record = self._approvals.get(approval_id)
        return record.to_dict() if record else None

    def register_callback(
        self,
        approval_id: str,
        callback: Callable[[Dict[str, Any]], Awaitable[None]],
    ) -> None:
        """Register a callback to fire when the approval is decided."""
        if approval_id not in self._callbacks:
            self._callbacks[approval_id] = []
        self._callbacks[approval_id].append(callback)

    async def _fire_callback(self, approval_id: str, record: Dict[str, Any]) -> None:
        callbacks = self._callbacks.pop(approval_id, [])
        for cb in callbacks:
            try:
                await cb(record)
            except Exception as exc:
                logger.error(
                    "Approval callback failed for %s: %s",
                    approval_id,
                    exc,
                )

    async def _timeout_loop(self) -> None:
        """Background loop that expires stale approvals."""
        while self._running:
            try:
                now = datetime.now(timezone.utc)
                expired_ids = [
                    aid
                    for aid, rec in self._approvals.items()
                    if rec.status == "PENDING" and rec.is_expired()
                ]
                for aid in expired_ids:
                    record = self._approvals[aid]
                    record.status = "TIMEOUT"
                    record.decided_at = now
                    record.comment = "Auto-rejected due to timeout"
                    logger.info(
                        "Approval %s timed out (expired after %d minutes)",
                        aid,
                        record.timeout_minutes,
                    )
                    await self._fire_callback(aid, record.to_dict())
                await asyncio.sleep(30)  # Check every 30 seconds
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("Approval timeout loop error: %s", exc)
                await asyncio.sleep(60)


# Module-level singleton
approval_service = ApprovalService()

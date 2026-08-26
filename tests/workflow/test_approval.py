"""Tests for ApprovalService — Phase 9."""

from __future__ import annotations

from typing import Any, Dict, List

import pytest

from app.workflow_engine.approval import ApprovalRecord, ApprovalService


class TestApprovalRecord:
    def test_initial_state(self) -> None:
        rec = ApprovalRecord(
            approval_id="a1",
            workflow_id="wf1",
            run_id="r1",
            node_name="review",
            approvers=["admin"],
            message="Approve?",
        )
        assert rec.status == "PENDING"
        assert rec.is_expired() is False

    def test_to_dict_includes_all_fields(self) -> None:
        rec = ApprovalRecord(
            approval_id="a1",
            workflow_id="wf1",
            run_id="r1",
            node_name="review",
            approvers=["admin"],
            message="Approve?",
            timeout_minutes=30,
            tenant_id="t1",
        )
        d = rec.to_dict()
        assert d["id"] == "a1"
        assert d["workflow_id"] == "wf1"
        assert d["status"] == "PENDING"
        assert d["timeout_minutes"] == 30
        assert d["tenant_id"] == "t1"

    def test_is_expired(self) -> None:
        rec = ApprovalRecord(
            approval_id="a1",
            workflow_id="wf1",
            run_id="r1",
            node_name="review",
            approvers=["admin"],
            message="Approve?",
            timeout_minutes=0,
        )
        assert rec.is_expired() is True


class TestApprovalService:
    @pytest.fixture
    async def service(self) -> ApprovalService:
        svc = ApprovalService()
        yield svc

    async def test_create_approval(self, service: ApprovalService) -> None:
        result = await service.create_approval(
            workflow_id="wf1",
            run_id="r1",
            node_name="review",
            approvers=["admin"],
            message="Approve this action?",
        )
        assert result["status"] == "PENDING"
        assert result["workflow_id"] == "wf1"
        assert "id" in result

    async def test_get_approval(self, service: ApprovalService) -> None:
        created = await service.create_approval(
            workflow_id="wf1",
            run_id="r1",
            node_name="review",
            approvers=["admin"],
            message="Approve?",
        )
        fetched = await service.get_approval(created["id"])
        assert fetched is not None
        assert fetched["id"] == created["id"]

    async def test_get_approval_not_found(self, service: ApprovalService) -> None:
        result = await service.get_approval("nonexistent")
        assert result is None

    async def test_approve(self, service: ApprovalService) -> None:
        created = await service.create_approval(
            workflow_id="wf1",
            run_id="r1",
            node_name="review",
            approvers=["admin"],
            message="Approve?",
        )
        result = await service.approve(created["id"], user_id="admin", comment="Looks good")
        assert result["status"] == "APPROVED"
        assert result["decided_by"] == "admin"
        assert result["comment"] == "Looks good"

    async def test_approve_not_found(self, service: ApprovalService) -> None:
        with pytest.raises(ValueError, match="not found"):
            await service.approve("nonexistent", user_id="admin")

    async def test_approve_already_decided(self, service: ApprovalService) -> None:
        created = await service.create_approval(
            workflow_id="wf1",
            run_id="r1",
            node_name="review",
            approvers=["admin"],
            message="Approve?",
        )
        await service.approve(created["id"], user_id="admin")
        with pytest.raises(ValueError, match="not pending"):
            await service.approve(created["id"], user_id="admin")

    async def test_reject(self, service: ApprovalService) -> None:
        created = await service.create_approval(
            workflow_id="wf1",
            run_id="r1",
            node_name="review",
            approvers=["admin"],
            message="Approve?",
        )
        result = await service.reject(created["id"], user_id="admin", comment="Not now")
        assert result["status"] == "REJECTED"
        assert result["comment"] == "Not now"

    async def test_reject_not_found(self, service: ApprovalService) -> None:
        with pytest.raises(ValueError, match="not found"):
            await service.reject("nonexistent", user_id="admin")

    async def test_reject_twice_raises(self, service: ApprovalService) -> None:
        created = await service.create_approval(
            workflow_id="wf1",
            run_id="r1",
            node_name="review",
            approvers=["admin"],
            message="Approve?",
        )
        await service.reject(created["id"], user_id="admin")
        with pytest.raises(ValueError, match="not pending"):
            await service.reject(created["id"], user_id="admin")

    async def test_callback_on_approve(self, service: ApprovalService) -> None:
        callback_called: List[Dict[str, Any]] = []

        async def cb(data: Dict[str, Any]) -> None:
            callback_called.append(data)

        created = await service.create_approval(
            workflow_id="wf1",
            run_id="r1",
            node_name="review",
            approvers=["admin"],
            message="Approve?",
        )
        service.register_callback(created["id"], cb)
        await service.approve(created["id"], user_id="admin")
        assert len(callback_called) == 1
        assert callback_called[0]["status"] == "APPROVED"

    async def test_callback_on_reject(self, service: ApprovalService) -> None:
        callback_called: List[Dict[str, Any]] = []

        async def cb(data: Dict[str, Any]) -> None:
            callback_called.append(data)

        created = await service.create_approval(
            workflow_id="wf1",
            run_id="r1",
            node_name="review",
            approvers=["admin"],
            message="Approve?",
        )
        service.register_callback(created["id"], cb)
        await service.reject(created["id"], user_id="admin")
        assert len(callback_called) == 1
        assert callback_called[0]["status"] == "REJECTED"

    async def test_multiple_callbacks(self, service: ApprovalService) -> None:
        calls: List[str] = []

        async def cb1(data: Dict[str, Any]) -> None:
            calls.append("cb1")

        async def cb2(data: Dict[str, Any]) -> None:
            calls.append("cb2")

        created = await service.create_approval(
            workflow_id="wf1",
            run_id="r1",
            node_name="review",
            approvers=["admin"],
            message="Approve?",
        )
        service.register_callback(created["id"], cb1)
        service.register_callback(created["id"], cb2)
        await service.approve(created["id"], user_id="admin")
        assert len(calls) == 2

    async def test_callback_error_does_not_crash(self, service: ApprovalService) -> None:
        async def failing_cb(data: Dict[str, Any]) -> None:
            raise RuntimeError("callback error")

        created = await service.create_approval(
            workflow_id="wf1",
            run_id="r1",
            node_name="review",
            approvers=["admin"],
            message="Approve?",
        )
        service.register_callback(created["id"], failing_cb)
        # Should not raise
        await service.approve(created["id"], user_id="admin")

    async def test_start_stop_timeout_loop(self, service: ApprovalService) -> None:
        await service.start()
        assert service._running is True
        assert service._timeout_task is not None
        await service.stop()
        assert service._running is False

    async def test_timeout_expires_approval(self, service: ApprovalService) -> None:
        created = await service.create_approval(
            workflow_id="wf1",
            run_id="r1",
            node_name="review",
            approvers=["admin"],
            message="Approve?",
            timeout_minutes=0,  # Immediately expired
        )
        rec = service._approvals.get(created["id"])
        assert rec is not None
        assert rec.is_expired() is True

    async def test_create_with_custom_timeout(self, service: ApprovalService) -> None:
        result = await service.create_approval(
            workflow_id="wf1",
            run_id="r1",
            node_name="review",
            approvers=["admin"],
            message="Approve?",
            timeout_minutes=120,
            tenant_id="t1",
            created_by="user1",
        )
        assert result["timeout_minutes"] == 120
        assert result["tenant_id"] == "t1"
        assert result["created_by"] == "user1"

"""Tests for workflow triggers — Phase 9."""

from __future__ import annotations

from typing import Any, Dict

import pytest

from app.workflow_engine.trigger import (
    ApiTrigger,
    ScheduleTrigger,
    SyncEventTrigger,
    TriggerManager,
    WebhookTrigger,
    default_trigger_manager,
)


class TestApiTrigger:
    async def test_validate_always_true(self) -> None:
        trigger = ApiTrigger()
        assert await trigger.validate({}) is True
        assert await trigger.validate({"data": "test"}) is True

    async def test_extract_context(self) -> None:
        trigger = ApiTrigger()
        ctx = await trigger.extract_context({"key": "value"})
        assert ctx["trigger_type"] == "api"
        assert ctx["payload"]["key"] == "value"


class TestWebhookTrigger:
    async def test_validate_without_secret(self) -> None:
        trigger = WebhookTrigger()
        assert await trigger.validate({}) is True

    async def test_validate_with_secret_and_correct_signature(self) -> None:
        import hashlib
        import hmac
        import json

        secret = "my_secret"
        payload = {"event": "push"}
        sig = hmac.new(
            secret.encode(),
            json.dumps(payload, sort_keys=True).encode(),
            hashlib.sha256,
        ).hexdigest()

        trigger = WebhookTrigger({"secret": secret})
        assert await trigger.validate(payload, {"x-webhook-signature": sig}) is True

    async def test_validate_with_secret_and_wrong_signature(self) -> None:
        trigger = WebhookTrigger({"secret": "my_secret"})
        assert await trigger.validate({}, {"x-webhook-signature": "wrong"}) is False

    async def test_validate_missing_header(self) -> None:
        trigger = WebhookTrigger({"secret": "s"})
        assert await trigger.validate({}) is False

    async def test_extract_context(self) -> None:
        trigger = WebhookTrigger()
        ctx = await trigger.extract_context({"event": "push"})
        assert ctx["trigger_type"] == "webhook"


class TestScheduleTrigger:
    async def test_validate_always_true(self) -> None:
        trigger = ScheduleTrigger()
        assert await trigger.validate({}) is True

    async def test_extract_context(self) -> None:
        trigger = ScheduleTrigger()
        ctx = await trigger.extract_context({})
        assert ctx["trigger_type"] == "schedule"
        assert "scheduled_at" in ctx


class TestSyncEventTrigger:
    async def test_validate_allowed_event(self) -> None:
        trigger = SyncEventTrigger({"event_types": ["git_push", "doc_sync"]})
        assert await trigger.validate({"event_type": "git_push"}) is True

    async def test_validate_disallowed_event(self) -> None:
        trigger = SyncEventTrigger({"event_types": ["git_push"]})
        assert await trigger.validate({"event_type": "unknown"}) is False

    async def test_validate_no_filter(self) -> None:
        trigger = SyncEventTrigger()
        assert await trigger.validate({"event_type": "anything"}) is True

    async def test_extract_context(self) -> None:
        trigger = SyncEventTrigger()
        ctx = await trigger.extract_context({"event_type": "git_push", "source": "gitlab"})
        assert ctx["trigger_type"] == "sync_event"
        assert ctx["source"] == "gitlab"


class TestTriggerManager:
    async def test_register_and_get(self) -> None:
        mgr = TriggerManager()
        mgr.register("api", ApiTrigger())
        assert mgr.get("api") is not None
        assert mgr.get("unknown") is None

    async def test_validate_trigger(self) -> None:
        mgr = TriggerManager()
        mgr.register("api", ApiTrigger())
        assert await mgr.validate_trigger("api", {}) is True
        assert await mgr.validate_trigger("unknown", {}) is False

    async def test_extract_context(self) -> None:
        mgr = TriggerManager()
        mgr.register("api", ApiTrigger())
        ctx = await mgr.extract_context("api", {"k": "v"})
        assert ctx["trigger_type"] == "api"

    async def test_extract_context_fallback(self) -> None:
        mgr = TriggerManager()
        ctx = await mgr.extract_context("unknown", {"k": "v"})
        assert ctx["trigger_type"] == "unknown"
        assert ctx["payload"] == {"k": "v"}


class TestDefaultTriggerManager:
    async def test_has_all_trigger_types(self) -> None:
        assert default_trigger_manager.get("api") is not None
        assert default_trigger_manager.get("webhook") is not None
        assert default_trigger_manager.get("schedule") is not None
        assert default_trigger_manager.get("sync_event") is not None
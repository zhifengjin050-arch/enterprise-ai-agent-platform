"""Workflow event triggers — Phase 9.

Supports:
    API Trigger        — manual / API-invoked
    Webhook Trigger    — external webhook payload
    Schedule Trigger   — cron-based scheduling
    SyncEvent Trigger  — internal sync engine events
"""
from __future__ import annotations

import abc
import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Trigger base
# ──────────────────────────────────────────────


class Trigger(abc.ABC):
    """Abstract base for all workflow triggers."""

    def __init__(self, trigger_config: Optional[Dict[str, Any]] = None) -> None:
        self.config = trigger_config or {}

    @abc.abstractmethod
    async def validate(
        self, payload: Dict[str, Any], headers: Optional[Dict[str, str]] = None
    ) -> bool:
        """Validate whether the trigger should fire."""

    @abc.abstractmethod
    async def extract_context(
        self, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extract workflow context variables from payload."""

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}>"


# ──────────────────────────────────────────────
# API Trigger
# ──────────────────────────────────────────────


class ApiTrigger(Trigger):
    """Manual or API-triggered workflow execution.

    Always validates to True — the caller is trusted through API auth.
    """

    async def validate(
        self, payload: Dict[str, Any], headers: Optional[Dict[str, str]] = None
    ) -> bool:
        return True

    async def extract_context(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return {"payload": payload, "trigger_type": "api"}


# ──────────────────────────────────────────────
# Webhook Trigger
# ──────────────────────────────────────────────


class WebhookTrigger(Trigger):
    """Validates incoming webhooks with HMAC signature verification.

    Config:
        secret: str — HMAC secret for signature verification
        signature_header: str — header name containing the signature (default X-Webhook-Signature)
        allowed_methods: list[str] — allowed HTTP methods
    """

    async def validate(
        self, payload: Dict[str, Any], headers: Optional[Dict[str, str]] = None
    ) -> bool:
        secret = self.config.get("secret", "")
        if not secret:
            logger.warning("WebhookTrigger has no secret configured — skipping validation")
            return True

        headers = headers or {}
        sig_header = self.config.get("signature_header", "X-Webhook-Signature")
        received_sig = headers.get(sig_header.lower(), headers.get(sig_header, ""))
        if not received_sig:
            logger.warning("WebhookTrigger missing signature header %s", sig_header)
            return False

        # HMAC-SHA256
        expected_sig = hmac.new(
            secret.encode("utf-8"),
            json.dumps(payload, sort_keys=True).encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(received_sig, expected_sig)

    async def extract_context(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return {"payload": payload, "trigger_type": "webhook"}


# ──────────────────────────────────────────────
# Schedule Trigger
# ──────────────────────────────────────────────


class ScheduleTrigger(Trigger):
    """Cron-based scheduled execution.

    Config:
        cron: str — cron expression (e.g. "0 */2 * * *")
        timezone: str — timezone (default UTC)
    """

    async def validate(
        self, payload: Dict[str, Any], headers: Optional[Dict[str, str]] = None
    ) -> bool:
        # Schedule triggers are evaluated by a scheduler loop, not by payload
        return True

    async def extract_context(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        now = datetime.now(timezone.utc)
        return {
            "trigger_type": "schedule",
            "scheduled_at": now.isoformat(),
            "payload": payload,
        }


# ──────────────────────────────────────────────
# SyncEvent Trigger
# ──────────────────────────────────────────────


class SyncEventTrigger(Trigger):
    """Fires on internal sync engine events (e.g. GitLab commit, document sync).

    Config:
        event_types: list[str] — which sync event types to react to
    """

    async def validate(
        self, payload: Dict[str, Any], headers: Optional[Dict[str, str]] = None
    ) -> bool:
        allowed = self.config.get("event_types", [])
        event_type = payload.get("event_type", "")
        if allowed and event_type not in allowed:
            return False
        return True

    async def extract_context(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "trigger_type": "sync_event",
            "event_type": payload.get("event_type", "unknown"),
            "source": payload.get("source", ""),
            "payload": payload,
        }


# ──────────────────────────────────────────────
# Trigger Manager
# ──────────────────────────────────────────────


class TriggerManager:
    """Manages trigger validation and context extraction."""

    def __init__(self) -> None:
        self._triggers: Dict[str, Trigger] = {}

    def register(self, trigger_type: str, trigger: Trigger) -> None:
        self._triggers[trigger_type] = trigger

    def get(self, trigger_type: str) -> Optional[Trigger]:
        return self._triggers.get(trigger_type)

    async def validate_trigger(
        self,
        trigger_type: str,
        payload: Dict[str, Any],
        headers: Optional[Dict[str, str]] = None,
    ) -> bool:
        trigger = self.get(trigger_type)
        if trigger is None:
            logger.warning("No trigger registered for type '%s'", trigger_type)
            return False
        return await trigger.validate(payload, headers)

    async def extract_context(
        self,
        trigger_type: str,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        trigger = self.get(trigger_type)
        if trigger is None:
            return {"payload": payload, "trigger_type": trigger_type}
        return await trigger.extract_context(payload)


# Default manager with built-in triggers
default_trigger_manager = TriggerManager()
default_trigger_manager.register("api", ApiTrigger())
default_trigger_manager.register("webhook", WebhookTrigger())
default_trigger_manager.register("schedule", ScheduleTrigger())
default_trigger_manager.register("sync_event", SyncEventTrigger())

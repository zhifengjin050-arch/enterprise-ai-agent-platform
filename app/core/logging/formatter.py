"""
Structured JSON log formatter — Phase 8 Observability upgrade.

Produces JSON lines suitable for log aggregation systems.
Each log record is serialised as a single JSON object per line
with mandatory service, trace_id, tenant_id, request_id fields.

Example output:
    {"time": "2026-08-18T12:00:00Z", "level": "INFO", "module": "app.api.health",
     "service": "enterprise-knowledge-agent",
     "trace_id": "abc...", "tenant_id": "t1", "request_id": "req-123",
     "message": "Health check passed"}
"""

from __future__ import annotations

import json
import logging
import traceback
from datetime import datetime, timezone
from typing import Any

_SERVICE_NAME = "enterprise-knowledge-agent"


class StructuredFormatter(logging.Formatter):
    """JSON log formatter with mandatory observability fields.

    Always includes:
      - timestamp, level, module, message
      - service (constant)
      - request_id (from extra or request state)
      - trace_id (from OpenTelemetry if available)
      - tenant_id (from TenantContext if available)
      - user_id (from TenantContext if available)
    """

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            "level": record.levelname,
            "service": _SERVICE_NAME,
            "module": record.name,
            "message": record.getMessage(),
        }

        # Attach request_id if available via extra
        request_id: str | None = getattr(record, "request_id", None)
        if request_id:
            log_entry["request_id"] = request_id

        # Try to capture trace_id from OpenTelemetry if active
        try:
            from app.observability.trace import TraceManager

            tid = TraceManager.get_trace_id()
            if tid:
                log_entry["trace_id"] = tid
        except Exception:
            pass

        # Attach tenant_id / user_id from TenantContext if extra provided
        tid_ctx: str | None = getattr(record, "tenant_id", None)
        if tid_ctx:
            log_entry["tenant_id"] = tid_ctx
        uid_ctx: str | None = getattr(record, "user_id", None)
        if uid_ctx:
            log_entry["user_id"] = uid_ctx

        # Attach any additional extra fields (excluding standard LogRecord attrs)
        standard_attrs = {
            "args",
            "asctime",
            "created",
            "exc_info",
            "exc_text",
            "filename",
            "funcName",
            "levelname",
            "levelno",
            "lineno",
            "module",
            "msecs",
            "message",
            "msg",
            "name",
            "pathname",
            "process",
            "processName",
            "relativeCreated",
            "stack_info",
            "thread",
            "threadName",
            "request_id",
            "tenant_id",
            "user_id",
        }
        extra: dict[str, Any] = {
            k: v for k, v in record.__dict__.items() if k not in standard_attrs
        }
        if extra:
            log_entry["extra"] = extra

        # Exception traceback
        if record.exc_info and record.exc_info[0] is not None:
            log_entry["exception"] = traceback.format_exception(*record.exc_info)

        return json.dumps(log_entry, default=str)

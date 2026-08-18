"""Tests for Phase 8 structured logging upgrade."""

from __future__ import annotations

import json
import logging
from io import StringIO

from app.core.logging.formatter import StructuredFormatter


class TestStructuredFormatterV2:
    """StructuredFormatter Phase 8 upgrade tests."""

    def setup_method(self):
        self.formatter = StructuredFormatter()
        self.stream = StringIO()
        self.handler = logging.StreamHandler(self.stream)
        self.handler.setFormatter(self.formatter)
        self.logger = logging.getLogger("test.observability")
        self.logger.setLevel(logging.DEBUG)
        self.logger.handlers = [self.handler]
        self.logger.propagate = False

    def get_last_log(self) -> dict:
        return json.loads(self.stream.getvalue().strip())

    def test_timestamp_field_present(self):
        self.logger.info("test message")
        log = self.get_last_log()
        assert "timestamp" in log
        assert log["timestamp"].endswith("Z")

    def test_level_field_present(self):
        self.logger.warning("warn")
        log = self.get_last_log()
        assert log["level"] == "WARNING"

    def test_service_field_present(self):
        self.logger.info("test")
        log = self.get_last_log()
        assert log["service"] == "enterprise-knowledge-agent"

    def test_module_field_present(self):
        self.logger.info("test")
        log = self.get_last_log()
        assert "module" in log
        assert log["module"] == "test.observability"

    def test_message_field_present(self):
        self.logger.info("hello observability")
        log = self.get_last_log()
        assert log["message"] == "hello observability"

    def test_request_id_via_extra(self):
        self.logger.info("req", extra={"request_id": "req-123"})
        log = self.get_last_log()
        assert log["request_id"] == "req-123"

    def test_tenant_id_via_extra(self):
        self.logger.info("tenant", extra={"tenant_id": "t-001"})
        log = self.get_last_log()
        assert log["tenant_id"] == "t-001"

    def test_user_id_via_extra(self):
        self.logger.info("user", extra={"user_id": "u-001"})
        log = self.get_last_log()
        assert log["user_id"] == "u-001"

    def test_extra_fields_separate(self):
        self.logger.info("extra", extra={"custom_key": "custom_val"})
        log = self.get_last_log()
        assert "extra" in log
        assert log["extra"]["custom_key"] == "custom_val"

    def test_exception_traceback(self):
        try:
            raise ValueError("test error")
        except ValueError:
            self.logger.exception("err occurred")
        log = self.get_last_log()
        assert "exception" in log
        assert "ValueError" in "".join(log["exception"])

    def test_json_output_valid(self):
        self.logger.info("valid json")
        raw = self.stream.getvalue().strip()
        parsed = json.loads(raw)
        assert isinstance(parsed, dict)

    def test_no_standard_attrs_in_extra(self):
        self.logger.info("clean extra")
        log = self.get_last_log()
        extra = log.get("extra", {})
        # args should not appear in extra
        assert "args" not in extra
        assert "msg" not in extra
        assert "message" not in extra
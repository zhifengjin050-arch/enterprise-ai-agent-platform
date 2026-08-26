"""Tests for structured logging configuration.

Verifies:
1. configure_logging sets up handlers correctly
2. StructuredFormatter produces valid JSON
3. get_logger returns proper logger instances
"""

from __future__ import annotations

import json
import logging

from app.core.logging import configure_logging, get_logger
from app.core.logging.formatter import StructuredFormatter


class TestConfigureLogging:
    """Tests for configure_logging()."""

    def test_sets_root_level(self) -> None:
        configure_logging(level="DEBUG")
        assert logging.getLogger().level == logging.DEBUG

    def test_adds_stream_handler(self) -> None:
        configure_logging(level="INFO")
        root = logging.getLogger()
        handlers = [h for h in root.handlers if not isinstance(h, logging.NullHandler)]
        assert len(handlers) >= 1


class TestStructuredFormatter:
    """Tests for StructuredFormatter JSON output."""

    def test_basic_format(self) -> None:
        formatter = StructuredFormatter()
        record = logging.LogRecord(
            name="test.module",
            level=logging.INFO,
            pathname="/test.py",
            lineno=42,
            msg="Hello %s",
            args=("world",),
            exc_info=None,
        )
        output = formatter.format(record)
        data = json.loads(output)
        assert data["level"] == "INFO"
        assert data["module"] == "test.module"
        assert data["message"] == "Hello world"
        assert "timestamp" in data or "time" in data

    def test_request_id_in_extra(self) -> None:
        formatter = StructuredFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="/test.py",
            lineno=1,
            msg="test",
            args=(),
            exc_info=None,
        )
        record.request_id = "req-123"  # type: ignore[attr-defined]
        output = formatter.format(record)
        data = json.loads(output)
        assert data["request_id"] == "req-123"

    def test_user_id_in_extra(self) -> None:
        formatter = StructuredFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="/test.py",
            lineno=1,
            msg="test",
            args=(),
            exc_info=None,
        )
        record.user_id = "user-456"  # type: ignore[attr-defined]
        output = formatter.format(record)
        data = json.loads(output)
        assert data["user_id"] == "user-456"

    def test_extra_fields(self) -> None:
        formatter = StructuredFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="/test.py",
            lineno=1,
            msg="test",
            args=(),
            exc_info=None,
        )
        record.custom_field = "custom_value"  # type: ignore[attr-defined]
        output = formatter.format(record)
        data = json.loads(output)
        assert data["extra"]["custom_field"] == "custom_value"


class TestGetLogger:
    """Tests for get_logger()."""

    def test_returns_logger_instance(self) -> None:
        logger = get_logger(__name__)
        assert isinstance(logger, logging.Logger)

    def test_logger_name_matches(self) -> None:
        logger = get_logger("my.custom.module")
        assert logger.name == "my.custom.module"

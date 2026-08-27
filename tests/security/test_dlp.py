"""DLP and connector secret redaction tests."""

from __future__ import annotations

from app.security.dlp import (
    is_blocked_mcp_tool,
    redact_mapping,
    redact_text,
    scan_text,
)


def test_scan_detects_password_assignment() -> None:
    findings = scan_text("password: hunter2")
    assert findings
    assert findings[0].kind == "secret_assignment"


def test_redact_password() -> None:
    text, findings = redact_text("password=hunter2")
    assert findings
    assert "hunter2" not in text
    assert "[REDACTED]" in text


def test_redact_connector_config() -> None:
    masked = redact_mapping({"app_id": "cli_xxx", "app_secret": "s3cret", "token": "abc"})
    assert masked["app_id"] == "cli_xxx"
    assert masked["app_secret"] == "[REDACTED]"
    assert masked["token"] == "[REDACTED]"


def test_block_ssh_mcp_tool() -> None:
    assert is_blocked_mcp_tool("ssh_execute_command") is True
    assert is_blocked_mcp_tool("k8s_get_pods") is False

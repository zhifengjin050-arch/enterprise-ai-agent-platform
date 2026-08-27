"""Secret scanning and redaction for knowledge ingest and tool output."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, List, Mapping, Sequence

_PEM_RE = re.compile(
    r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----[\s\S]+?-----END (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"
)
_AWS_KEY_RE = re.compile(r"\bAKIA[0-9A-Z]{16}\b")
_GENERIC_ASSIGN_RE = re.compile(
    r"(?i)\b(password|passwd|secret|api[_-]?key|token|private_key)\b\s*[:=]\s*([^\s#]+)"
)
_SSH_INLINE_RE = re.compile(r"(?i)ssh\s+pass(word)?\s*[:=]\s*\S+")

REDACTED = "[REDACTED]"


@dataclass(frozen=True)
class DlpFinding:
    kind: str
    span: str


def scan_text(text: str) -> List[DlpFinding]:
    """Return secret-like findings in ``text``."""
    if not text:
        return []
    findings: List[DlpFinding] = []
    for pattern, kind in (
        (_PEM_RE, "private_key"),
        (_AWS_KEY_RE, "aws_access_key"),
        (_SSH_INLINE_RE, "ssh_password"),
        (_GENERIC_ASSIGN_RE, "secret_assignment"),
    ):
        for match in pattern.finditer(text):
            findings.append(DlpFinding(kind=kind, span=match.group(0)[:80]))
    return findings


def redact_text(text: str) -> tuple[str, List[DlpFinding]]:
    """Replace secret material with ``[REDACTED]``."""
    findings = scan_text(text)
    if not text or not findings:
        return text or "", findings
    redacted = _PEM_RE.sub(REDACTED, text)
    redacted = _AWS_KEY_RE.sub(REDACTED, redacted)
    redacted = _SSH_INLINE_RE.sub("ssh password=[REDACTED]", redacted)

    def _assign(match: re.Match[str]) -> str:
        return f"{match.group(1)}={REDACTED}"

    redacted = _GENERIC_ASSIGN_RE.sub(_assign, redacted)
    return redacted, findings


SECRET_CONFIG_KEYS = {
    "token",
    "secret",
    "password",
    "passwd",
    "app_secret",
    "api_key",
    "apikey",
    "access_key",
    "private_key",
    "jwt_secret",
    "client_secret",
    "refresh_token",
}


def redact_mapping(data: Mapping[str, Any] | None) -> dict[str, Any]:
    """Mask secret-looking keys in a connector config (recursive)."""
    if not data:
        return {}
    out: dict[str, Any] = {}
    for key, value in data.items():
        lowered = str(key).lower()
        if any(part in lowered for part in SECRET_CONFIG_KEYS):
            out[key] = REDACTED if value not in (None, "") else value
        elif isinstance(value, Mapping):
            out[key] = redact_mapping(value)
        else:
            out[key] = value
    return out


def redact_tool_payload(data: Any) -> Any:
    """Recursively mask secrets in tool / retrieval payloads."""
    if isinstance(data, Mapping):
        return (
            redact_mapping(data)
            if _looks_like_config(data)
            else {k: redact_tool_payload(v) for k, v in data.items()}
        )
    if isinstance(data, list):
        return [redact_tool_payload(v) for v in data]
    if isinstance(data, str):
        redacted, _ = redact_text(data)
        return redacted
    return data


def _looks_like_config(data: Mapping[str, Any]) -> bool:
    keys = {str(k).lower() for k in data.keys()}
    return bool(keys & SECRET_CONFIG_KEYS)


BLOCKED_MCP_TOOLS: Sequence[str] = (
    "ssh",
    "secret",
    "password",
    "passwd",
    "credential",
    "kubeconfig",
    "private_key",
    "vault",
)


def is_blocked_mcp_tool(name: str) -> bool:
    lowered = (name or "").lower()
    return any(token in lowered for token in BLOCKED_MCP_TOOLS)

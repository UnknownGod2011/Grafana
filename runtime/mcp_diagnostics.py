"""Secret-aware, bounded diagnostics for untrusted MCP failure payloads.

This module is intentionally dependency-free so the release smoke can use it before
any application services are available. Diagnostics are for operator triage only:
they must never become a lossless serialization of an upstream payload.
"""
from __future__ import annotations

import re
from typing import Any

MAX_DIAGNOSTIC_CHARS = 2048
MAX_DIAGNOSTIC_DEPTH = 8
MAX_DIAGNOSTIC_ITEMS = 32
MAX_DIAGNOSTIC_STRING_CHARS = 512
_REDACTED = "<redacted>"

# Keys are normalized by removing punctuation so Authorization, api_key,
# x-api-key, access-token, etc. are covered without maintaining every spelling.
_SENSITIVE_KEY_PARTS = (
    "authorization", "credential", "password", "passwd", "secret", "token",
    "apikey", "cookie", "setcookie", "clientsecret", "privatekey",
)
_BEARER_RE = re.compile(r"(?i)\b(bearer)\s+[A-Za-z0-9._~+/=-]+")
_BASIC_RE = re.compile(r"(?i)\b(basic)\s+[A-Za-z0-9+/=]+")
_URL_CREDENTIAL_RE = re.compile(r"(?i)(https?://[^\s:/@]+:)[^\s@/]+(@)")
_ASSIGNMENT_RE = re.compile(
    r"(?i)\b(authorization|api[_-]?key|access[_-]?token|refresh[_-]?token|password|passwd|secret|token)"
    r"(\s*[:=]\s*)([^\s,;]+)"
)


def _sensitive_key(key: Any) -> bool:
    if not isinstance(key, str):
        return False
    normalized = "".join(ch for ch in key.lower() if ch.isalnum())
    return any(part in normalized for part in _SENSITIVE_KEY_PARTS)


def _safe_text(value: str) -> str:
    """Redact common inline credential forms and bound attacker-controlled text."""
    value = _BEARER_RE.sub(r"\1 " + _REDACTED, value)
    value = _BASIC_RE.sub(r"\1 " + _REDACTED, value)
    value = _URL_CREDENTIAL_RE.sub(r"\1" + _REDACTED + r"\2", value)
    value = _ASSIGNMENT_RE.sub(lambda m: m.group(1) + m.group(2) + _REDACTED, value)
    if len(value) > MAX_DIAGNOSTIC_STRING_CHARS:
        omitted = len(value) - MAX_DIAGNOSTIC_STRING_CHARS
        value = value[:MAX_DIAGNOSTIC_STRING_CHARS] + f"...<truncated {omitted} chars>"
    return value


def _sanitize(value: Any, *, depth: int = 0) -> Any:
    if depth > MAX_DIAGNOSTIC_DEPTH:
        return "<max-depth>"
    if isinstance(value, str):
        return _safe_text(value)
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for index, (key, child) in enumerate(value.items()):
            if index >= MAX_DIAGNOSTIC_ITEMS:
                sanitized["<truncated-items>"] = len(value) - MAX_DIAGNOSTIC_ITEMS
                break
            display_key = _safe_text(str(key))
            sanitized[display_key] = _REDACTED if _sensitive_key(key) else _sanitize(child, depth=depth + 1)
        return sanitized
    if isinstance(value, (list, tuple)):
        items = [_sanitize(child, depth=depth + 1) for child in value[:MAX_DIAGNOSTIC_ITEMS]]
        if len(value) > MAX_DIAGNOSTIC_ITEMS:
            items.append(f"<truncated {len(value) - MAX_DIAGNOSTIC_ITEMS} items>")
        return items
    # Never invoke arbitrary repr implementations from untrusted extension types.
    return f"<{type(value).__name__}>"


def safe_diagnostic(value: Any) -> str:
    """Return a bounded, secret-aware representation of an untrusted MCP value."""
    rendered = repr(_sanitize(value))
    if len(rendered) <= MAX_DIAGNOSTIC_CHARS:
        return rendered
    omitted = len(rendered) - MAX_DIAGNOSTIC_CHARS
    return rendered[:MAX_DIAGNOSTIC_CHARS] + f"...<truncated {omitted} chars>"

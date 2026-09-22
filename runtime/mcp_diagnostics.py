"""Secret-aware, bounded diagnostics for untrusted MCP failure payloads.

This module is intentionally dependency-free so the release smoke can use it before
any application services are available. Diagnostics are for operator triage only:
they must never become a lossless serialization of an upstream payload.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any

MAX_DIAGNOSTIC_CHARS = 2048
MAX_DIAGNOSTIC_DEPTH = 8
MAX_DIAGNOSTIC_ITEMS = 32
MAX_DIAGNOSTIC_STRING_CHARS = 512
MAX_TYPE_NAME_CHARS = 96
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
    if type(key) is not str:
        return False
    normalized = "".join(ch for ch in key.lower() if ch.isalnum())
    return any(part in normalized for part in _SENSITIVE_KEY_PARTS)


def _display_safe(value: str) -> str:
    """Neutralize terminal/log control and Unicode formatting characters."""
    parts: list[str] = []
    for ch in value:
        category = unicodedata.category(ch)
        if category in {"Cc", "Cf", "Cs", "Zl", "Zp"}:
            parts.append(f"\\u{ord(ch):04x}" if ord(ch) <= 0xFFFF else f"\\U{ord(ch):08x}")
        else:
            parts.append(ch)
    return "".join(parts)


def _safe_text(value: str) -> str:
    """Redact inline credentials, neutralize display controls, and bound text."""
    value = _BEARER_RE.sub(r"\1 " + _REDACTED, value)
    value = _BASIC_RE.sub(r"\1 " + _REDACTED, value)
    value = _URL_CREDENTIAL_RE.sub(r"\1" + _REDACTED + r"\2", value)
    value = _ASSIGNMENT_RE.sub(lambda m: m.group(1) + m.group(2) + _REDACTED, value)
    value = _display_safe(value)
    if len(value) > MAX_DIAGNOSTIC_STRING_CHARS:
        omitted = len(value) - MAX_DIAGNOSTIC_STRING_CHARS
        value = value[:MAX_DIAGNOSTIC_STRING_CHARS] + f"...<truncated {omitted} chars>"
    return value


def _safe_type_name(value: Any) -> str:
    """Return a bounded/display-safe type name without invoking value hooks.

    ``type(value).__name__`` is metadata on the class rather than an instance hook,
    but extension code can mutate it to contain terminal controls or enormous text.
    Keep opaque markers useful without creating a second log-spoofing surface.
    """
    name = type(value).__name__
    if type(name) is not str:
        return "unknown"
    name = _display_safe(name)
    if len(name) > MAX_TYPE_NAME_CHARS:
        name = name[:MAX_TYPE_NAME_CHARS] + "..."
    return name


def _safe_key(key: Any) -> str:
    """Render mapping keys without invoking attacker-controlled hooks."""
    if type(key) is str:
        return _safe_text(key)
    if key is None or type(key) in (bool, int, float):
        return _safe_text(str(key))
    return f"<{_safe_type_name(key)}-key>"


def _sanitize(value: Any, *, depth: int = 0) -> Any:
    if depth > MAX_DIAGNOSTIC_DEPTH:
        return "<max-depth>"
    # Exact built-in type checks are intentional. Container/scalar subclasses may
    # override iteration, slicing, len(), items(), or stringification hooks. MCP
    # JSON decoding produces plain built-ins; extension-defined subclasses are
    # therefore opaque diagnostic values rather than structures to traverse.
    if type(value) is str:
        return _safe_text(value)
    if value is None or type(value) in (bool, int, float):
        return value
    if type(value) is dict:
        sanitized: dict[str, Any] = {}
        for index, (key, child) in enumerate(value.items()):
            if index >= MAX_DIAGNOSTIC_ITEMS:
                sanitized["<truncated-items>"] = len(value) - MAX_DIAGNOSTIC_ITEMS
                break
            display_key = _safe_key(key)
            sanitized[display_key] = _REDACTED if _sensitive_key(key) else _sanitize(child, depth=depth + 1)
        return sanitized
    if type(value) in (list, tuple):
        items = [_sanitize(child, depth=depth + 1) for child in value[:MAX_DIAGNOSTIC_ITEMS]]
        if len(value) > MAX_DIAGNOSTIC_ITEMS:
            items.append(f"<truncated {len(value) - MAX_DIAGNOSTIC_ITEMS} items>")
        return items
    # Never invoke arbitrary repr/str/iteration implementations from untrusted extension types.
    return f"<{_safe_type_name(value)}>"


def safe_diagnostic(value: Any) -> str:
    """Return a bounded, secret-aware, display-safe representation of an MCP value."""
    rendered = repr(_sanitize(value))
    if len(rendered) <= MAX_DIAGNOSTIC_CHARS:
        return rendered
    omitted = len(rendered) - MAX_DIAGNOSTIC_CHARS
    return rendered[:MAX_DIAGNOSTIC_CHARS] + f"...<truncated {omitted} chars>"

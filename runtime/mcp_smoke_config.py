"""Bounded configuration parsing for the StageGuard Grafana MCP release smoke."""
from __future__ import annotations

import json

DEFAULT_EXPECTED_LABELS: dict[str, str] = {
    "production_id": "broadcast-alpha",
    "uplink": "uplink-b",
}
MAX_EXPECTED_LABELS_JSON_CHARS = 2048
MAX_EXPECTED_LABELS = 16
MAX_LABEL_CHARS = 128
# Unicode line/paragraph separators and bidi controls can visually rewrite operator logs
# even though they are not C0/C1 control characters.
_UNSAFE_DISPLAY_CODEPOINTS = frozenset(
    {
        0x2028,
        0x2029,
        0x202A,
        0x202B,
        0x202C,
        0x202D,
        0x202E,
        0x2066,
        0x2067,
        0x2068,
        0x2069,
    }
)


class SmokeConfigError(ValueError):
    """Raised when release-smoke configuration violates its bounded contract."""


def _contains_unsafe_display_char(value: str) -> bool:
    for char in value:
        codepoint = ord(char)
        if codepoint < 32 or 0x7F <= codepoint <= 0x9F or codepoint in _UNSAFE_DISPLAY_CODEPOINTS:
            return True
    return False


def expected_labels(raw: str | None) -> dict[str, str]:
    """Parse expected Prometheus series labels from bounded JSON.

    An unset/blank value uses the deterministic StageGuard demo identity. An explicit
    JSON object is required otherwise; empty objects are rejected because they would
    silently disable series-identity binding at the release boundary. Values are also
    display-safe because the normalized identity is emitted into release-smoke output.
    """
    if raw is None or not raw.strip():
        return dict(DEFAULT_EXPECTED_LABELS)
    if len(raw) > MAX_EXPECTED_LABELS_JSON_CHARS:
        raise SmokeConfigError(
            "STAGEGUARD_MCP_SMOKE_EXPECTED_LABELS exceeds the bounded configuration size"
        )
    try:
        decoded = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SmokeConfigError(
            "STAGEGUARD_MCP_SMOKE_EXPECTED_LABELS must be a JSON object of string labels"
        ) from exc
    if not isinstance(decoded, dict) or not decoded:
        raise SmokeConfigError(
            "STAGEGUARD_MCP_SMOKE_EXPECTED_LABELS must be a non-empty JSON object"
        )
    if len(decoded) > MAX_EXPECTED_LABELS:
        raise SmokeConfigError(
            f"STAGEGUARD_MCP_SMOKE_EXPECTED_LABELS may contain at most {MAX_EXPECTED_LABELS} labels"
        )

    labels: dict[str, str] = {}
    for key, value in decoded.items():
        if not isinstance(key, str) or not isinstance(value, str):
            raise SmokeConfigError("expected Prometheus label names and values must be strings")
        if not key or not value or len(key) > MAX_LABEL_CHARS or len(value) > MAX_LABEL_CHARS:
            raise SmokeConfigError(
                f"expected Prometheus label names and values must be 1..{MAX_LABEL_CHARS} characters"
            )
        if _contains_unsafe_display_char(key) or _contains_unsafe_display_char(value):
            raise SmokeConfigError(
                "expected Prometheus labels may not contain control or unsafe display characters"
            )
        labels[key] = value
    return labels

"""Bounded configuration parsing for the StageGuard Grafana MCP release smoke."""
from __future__ import annotations

import json
from typing import Mapping

DEFAULT_EXPECTED_LABELS: dict[str, str] = {
    "production_id": "broadcast-alpha",
    "uplink": "uplink-b",
}
MAX_EXPECTED_LABELS_JSON_CHARS = 2048
MAX_EXPECTED_LABELS = 16
MAX_LABEL_CHARS = 128


class SmokeConfigError(ValueError):
    """Raised when release-smoke configuration violates its bounded contract."""


def expected_labels(raw: str | None) -> dict[str, str]:
    """Parse expected Prometheus series labels from bounded JSON.

    An unset/blank value uses the deterministic StageGuard demo identity. An explicit
    JSON object is required otherwise; empty objects are rejected because they would
    silently disable series-identity binding at the release boundary.
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
        if any(ord(char) < 32 or ord(char) == 127 for char in key + value):
            raise SmokeConfigError("expected Prometheus labels may not contain control characters")
        labels[key] = value
    return labels

"""Bounded semantic validation for Prometheus evidence returned through Grafana MCP.

The parser is deliberately transport-tolerant: MCP content may contain JSON serialized
inside text blocks or already-structured objects. Acceptance is intentionally narrow:
a Prometheus-style sample must expose a finite timestamp and a finite numeric value.
"""
from __future__ import annotations

import json
import math
from typing import Any

MAX_EVIDENCE_NESTING_DEPTH = 16
MAX_JSON_TEXT_CHARS = 1_048_576


def _finite_number(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        return not isinstance(value, float) or math.isfinite(value)
    if isinstance(value, str):
        try:
            parsed = float(value.strip())
        except (TypeError, ValueError):
            return False
        return math.isfinite(parsed)
    return False


def _is_sample_pair(value: Any) -> bool:
    """Recognize Prometheus instant/range sample pairs: [timestamp, value]."""
    return isinstance(value, list) and len(value) == 2 and _finite_number(value[0]) and _finite_number(value[1])


def _decode_json_text(value: str) -> Any | None:
    if not value.strip() or len(value) > MAX_JSON_TEXT_CHARS:
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return None


def contains_prometheus_sample(value: Any, *, depth: int = 0) -> bool:
    """Return True only when bounded MCP evidence contains a real Prometheus sample.

    Supported representations include standard Prometheus ``value`` and ``values``
    fields, whether returned directly as structured MCP content or JSON-encoded text.
    Arbitrary numeric pairs elsewhere do not qualify.
    """
    if depth > MAX_EVIDENCE_NESTING_DEPTH:
        return False
    if isinstance(value, str):
        decoded = _decode_json_text(value)
        return decoded is not None and contains_prometheus_sample(decoded, depth=depth + 1)
    if isinstance(value, list):
        return any(contains_prometheus_sample(item, depth=depth + 1) for item in value)
    if not isinstance(value, dict):
        return False

    instant = value.get("value")
    if _is_sample_pair(instant):
        return True

    samples = value.get("values")
    if isinstance(samples, list) and any(_is_sample_pair(sample) for sample in samples):
        return True

    return any(contains_prometheus_sample(child, depth=depth + 1) for child in value.values())

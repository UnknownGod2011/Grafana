"""Bounded semantic validation for Prometheus evidence returned through Grafana MCP.

The parser is deliberately transport-tolerant: MCP content may contain JSON serialized
inside text blocks or already-structured objects. Acceptance follows the pinned official
mcp-grafana QueryPrometheusResult contract: samples must live under its ``data`` field
and belong to a Prometheus series object with a metric label map.
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


def _is_metric_map(value: Any) -> bool:
    """Require the label map carried by a Prometheus vector/matrix series."""
    return isinstance(value, dict) and all(isinstance(key, str) and isinstance(label, str) for key, label in value.items())


def _decode_json_text(value: str) -> Any | None:
    if not value.strip() or len(value) > MAX_JSON_TEXT_CHARS:
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return None


def _contains_sample_in_data(value: Any, *, depth: int) -> bool:
    """Inspect a QueryPrometheusResult.data subtree for real series-shaped samples."""
    if depth > MAX_EVIDENCE_NESTING_DEPTH:
        return False
    if isinstance(value, list):
        return any(_contains_sample_in_data(item, depth=depth + 1) for item in value)
    if not isinstance(value, dict):
        return False

    # Prometheus vector/matrix entries carry a metric label map alongside value(s).
    # Requiring that sibling prevents arbitrary nested objects under `data` from
    # masquerading as telemetry merely because they contain a numeric `value` pair.
    if _is_metric_map(value.get("metric")):
        instant = value.get("value")
        if _is_sample_pair(instant):
            return True

        samples = value.get("values")
        if isinstance(samples, list) and any(_is_sample_pair(sample) for sample in samples):
            return True

    return any(_contains_sample_in_data(child, depth=depth + 1) for child in value.values())


def contains_prometheus_sample(value: Any, *, depth: int = 0) -> bool:
    """Return True only for a sample in an official Grafana MCP query envelope.

    mcp-grafana v1.4.1 returns ``QueryPrometheusResult`` with ``data``, optional
    ``hints``, and optional ``warnings``. MCP may serialize that object into a text
    content block or expose structured content. Only series-shaped descendants of
    ``data`` can establish telemetry evidence; sample-looking values elsewhere cannot.
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

    if "data" in value and _contains_sample_in_data(value["data"], depth=depth + 1):
        return True

    # Traverse transport/envelope objects to locate QueryPrometheusResult, but never
    # treat arbitrary value/values fields outside its data subtree as evidence.
    return any(contains_prometheus_sample(child, depth=depth + 1) for child in value.values())

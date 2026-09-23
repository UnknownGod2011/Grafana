"""Bounded semantic validation for Prometheus evidence returned through Grafana MCP.

The parser is deliberately transport-tolerant: MCP content may contain JSON serialized
inside text blocks or already-structured objects. Acceptance follows the pinned official
mcp-grafana v1.4.1 QueryPrometheusResult contract: ``data`` is a Prometheus
``model.Value``. StageGuard's release probe intentionally accepts only vector/matrix
series, represented as a top-level list of objects with a metric label map and value(s).
Scalar/string model values are not sufficient evidence for the StageGuard series probe.

This module is a trust boundary. Structured values are accepted only when they are exact
JSON-like built-ins. Extension-defined subclasses are opaque so evidence validation does
not execute attacker-controlled container/scalar hooks while inspecting an MCP response.
"""
from __future__ import annotations

import json
import math
from collections.abc import Mapping
from typing import Any

MAX_EVIDENCE_NESTING_DEPTH = 16
MAX_JSON_TEXT_CHARS = 1_048_576
_MCP_PAYLOAD_KEYS = frozenset({"content", "text", "structuredContent", "result"})
_MCP_CONTENT_TYPES = frozenset({"text", "image", "audio", "resource", "resource_link"})


def _finite_timestamp(value: Any) -> bool:
    value_type = type(value)
    if value_type is int:
        return True
    return value_type is float and math.isfinite(value)


def _finite_sample_value(value: Any) -> bool:
    value_type = type(value)
    if value_type is int:
        return True
    if value_type is float:
        return math.isfinite(value)
    if value_type is str:
        try:
            parsed = float(value.strip())
        except (TypeError, ValueError):
            return False
        return math.isfinite(parsed)
    return False


def _is_sample_pair(value: Any) -> bool:
    return type(value) is list and len(value) == 2 and _finite_timestamp(value[0]) and _finite_sample_value(value[1])


def _is_metric_map(value: Any) -> bool:
    return type(value) is dict and all(type(key) is str and type(label) is str for key, label in value.items())


def _normalize_expected_labels(expected_labels: Mapping[str, str] | None) -> dict[str, str] | None:
    if expected_labels is None:
        return None
    if type(expected_labels) is not dict:
        return None
    if not all(type(key) is str and type(value) is str for key, value in expected_labels.items()):
        return None
    return dict(expected_labels)


def _metric_matches_expected_labels(metric: dict[str, str], expected_labels: dict[str, str] | None) -> bool:
    if expected_labels is None:
        return True
    return all(metric.get(key) == value for key, value in expected_labels.items())


def _decode_json_text(value: str) -> Any | None:
    if not value.strip() or len(value) > MAX_JSON_TEXT_CHARS:
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return None


def _series_has_sample(value: Any, expected_labels: dict[str, str] | None) -> bool:
    if type(value) is not dict or not _is_metric_map(value.get("metric")):
        return False
    metric = value["metric"]
    if not _metric_matches_expected_labels(metric, expected_labels):
        return False
    if _is_sample_pair(value.get("value")):
        return True
    samples = value.get("values")
    return type(samples) is list and any(_is_sample_pair(sample) for sample in samples)


def _data_contains_series_sample(value: Any, expected_labels: dict[str, str] | None) -> bool:
    return type(value) is list and any(_series_has_sample(series, expected_labels) for series in value)


def _is_mcp_content_block(value: dict[Any, Any]) -> bool:
    block_type = value.get("type")
    return type(block_type) is str and block_type in _MCP_CONTENT_TYPES


def _embedded_resource_payload(value: dict[Any, Any]) -> str | None:
    """Return JSON-capable text from a standards-shaped MCP EmbeddedResource.

    ResourceContents carries its payload in ``text`` or ``blob``. StageGuard only admits
    exact-string ``text`` because query evidence is JSON; arbitrary resource extension
    fields and binary blobs are deliberately non-evidentiary.
    """
    resource = value.get("resource")
    if type(resource) is not dict:
        return None
    text = resource.get("text")
    return text if type(text) is str else None


def contains_prometheus_sample(
    value: Any,
    *,
    expected_labels: Mapping[str, str] | None = None,
    depth: int = 0,
) -> bool:
    """Return True only for a qualifying series sample in a Grafana MCP query envelope."""
    normalized_labels = _normalize_expected_labels(expected_labels)
    if expected_labels is not None and normalized_labels is None:
        return False
    if depth > MAX_EVIDENCE_NESTING_DEPTH:
        return False

    value_type = type(value)
    if value_type is str:
        decoded = _decode_json_text(value)
        return decoded is not None and contains_prometheus_sample(decoded, expected_labels=normalized_labels, depth=depth + 1)
    if value_type is list:
        return any(contains_prometheus_sample(item, expected_labels=normalized_labels, depth=depth + 1) for item in value)
    if value_type is not dict:
        return False

    if _is_mcp_content_block(value):
        block_type = value.get("type")
        if block_type == "text":
            payload = value.get("text")
            return type(payload) is str and contains_prometheus_sample(payload, expected_labels=normalized_labels, depth=depth + 1)
        if block_type == "resource":
            payload = _embedded_resource_payload(value)
            return payload is not None and contains_prometheus_sample(payload, expected_labels=normalized_labels, depth=depth + 1)
        return False

    if "data" in value and _data_contains_series_sample(value["data"], normalized_labels):
        return True

    return any(
        contains_prometheus_sample(value[key], expected_labels=normalized_labels, depth=depth + 1)
        for key in _MCP_PAYLOAD_KEYS
        if key in value
    )

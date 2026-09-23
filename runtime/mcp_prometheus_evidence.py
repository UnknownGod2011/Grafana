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
Traversal is cardinality- and scalar-size-bounded so a syntactically valid but oversized
MCP response cannot force unbounded Python work during release acceptance. JSON text with
duplicate object keys or non-standard numeric constants is rejected to avoid parser-
differential ambiguity at the evidence boundary.
"""
from __future__ import annotations

import json
import math
from collections.abc import Mapping
from typing import Any

MAX_EVIDENCE_NESTING_DEPTH = 16
MAX_JSON_TEXT_CHARS = 1_048_576
MAX_MCP_COLLECTION_ITEMS = 128
MAX_PROMETHEUS_SERIES = 256
MAX_SAMPLES_PER_SERIES = 4_096
MAX_LABELS_PER_SERIES = 128
MAX_SAMPLE_VALUE_CHARS = 128
MAX_LABEL_NAME_CHARS = 1_024
MAX_LABEL_VALUE_CHARS = 4_096
_MCP_PAYLOAD_KEYS = frozenset({"content", "text", "structuredContent", "result"})
_MCP_CONTENT_TYPES = frozenset({"text", "image", "audio", "resource", "resource_link"})


class _AmbiguousJson(ValueError):
    """Internal signal for JSON that is not unambiguous RFC-compatible evidence."""


def _unique_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _AmbiguousJson(f"duplicate member: {key}")
        result[key] = value
    return result


def _reject_json_constant(token: str) -> Any:
    raise _AmbiguousJson(f"non-standard numeric constant: {token}")


def _finite_builtin_number(value: Any) -> bool:
    """Accept only exact built-in numbers representable as finite float64 values.

    Prometheus timestamps and samples originate from float64-oriented model values. A
    structured transport can otherwise inject an arbitrary-precision Python ``int`` that
    bypasses JSON decoder digit guards and is not representable by the upstream model.
    """
    value_type = type(value)
    if value_type is float:
        return math.isfinite(value)
    if value_type is not int:
        return False
    try:
        return math.isfinite(float(value))
    except OverflowError:
        return False


def _finite_timestamp(value: Any) -> bool:
    return _finite_builtin_number(value)


def _finite_sample_value(value: Any) -> bool:
    if _finite_builtin_number(value):
        return True
    if type(value) is str:
        if len(value) > MAX_SAMPLE_VALUE_CHARS:
            return False
        try:
            parsed = float(value.strip())
        except (TypeError, ValueError):
            return False
        return math.isfinite(parsed)
    return False


def _is_sample_pair(value: Any) -> bool:
    return type(value) is list and len(value) == 2 and _finite_timestamp(value[0]) and _finite_sample_value(value[1])


def _valid_label_pair(key: Any, value: Any) -> bool:
    return type(key) is str and type(value) is str and len(key) <= MAX_LABEL_NAME_CHARS and len(value) <= MAX_LABEL_VALUE_CHARS


def _is_metric_map(value: Any) -> bool:
    return type(value) is dict and len(value) <= MAX_LABELS_PER_SERIES and all(_valid_label_pair(key, label) for key, label in value.items())


def _normalize_expected_labels(expected_labels: Mapping[str, str] | None) -> dict[str, str] | None:
    if expected_labels is None:
        return None
    if type(expected_labels) is not dict or len(expected_labels) > MAX_LABELS_PER_SERIES:
        return None
    if not all(_valid_label_pair(key, value) for key, value in expected_labels.items()):
        return None
    return dict(expected_labels)


def _metric_matches_expected_labels(metric: dict[str, str], expected_labels: dict[str, str] | None) -> bool:
    if expected_labels is None:
        return True
    return all(metric.get(key) == value for key, value in expected_labels.items())


def _decode_json_text(value: str) -> Any | None:
    if len(value) > MAX_JSON_TEXT_CHARS or not value.strip():
        return None
    try:
        return json.loads(value, object_pairs_hook=_unique_json_object, parse_constant=_reject_json_constant)
    except (json.JSONDecodeError, RecursionError, ValueError):
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
    if type(samples) is not list or len(samples) > MAX_SAMPLES_PER_SERIES:
        return False
    return any(_is_sample_pair(sample) for sample in samples)


def _data_contains_series_sample(value: Any, expected_labels: dict[str, str] | None) -> bool:
    if type(value) is not list or len(value) > MAX_PROMETHEUS_SERIES:
        return False
    return any(_series_has_sample(series, expected_labels) for series in value)


def _is_mcp_content_block(value: dict[Any, Any]) -> bool:
    block_type = value.get("type")
    return type(block_type) is str and block_type in _MCP_CONTENT_TYPES


def _embedded_resource_payload(value: dict[Any, Any]) -> str | None:
    resource = value.get("resource")
    if type(resource) is not dict:
        return None
    text = resource.get("text")
    return text if type(text) is str else None


def contains_prometheus_sample(value: Any, *, expected_labels: Mapping[str, str] | None = None, depth: int = 0) -> bool:
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
        if len(value) > MAX_MCP_COLLECTION_ITEMS:
            return False
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

    return any(contains_prometheus_sample(value[key], expected_labels=normalized_labels, depth=depth + 1) for key in _MCP_PAYLOAD_KEYS if key in value)

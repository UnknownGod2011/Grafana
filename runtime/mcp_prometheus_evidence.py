"""Bounded semantic validation for Prometheus evidence returned through Grafana MCP.

The parser is deliberately transport-tolerant: MCP content may contain JSON serialized
inside text blocks or already-structured objects. Acceptance follows the pinned official
mcp-grafana v1.4.1 QueryPrometheusResult contract: ``data`` is a Prometheus
``model.Value``. StageGuard's release probe intentionally accepts only vector/matrix
series, represented as a top-level list of objects with a metric label map and value(s).
Scalar/string model values are not sufficient evidence for the StageGuard series probe.

Callers may additionally bind acceptance to expected metric labels. This prevents a
successful query transport from being mistaken for proof of the requested StageGuard
series when an unrelated series is returned.

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
_MCP_PAYLOAD_KEYS = frozenset({"content", "text", "resource", "structuredContent", "result"})


def _finite_number(value: Any) -> bool:
    # Exact built-ins only: bool is never numeric evidence, and subclasses may override
    # conversion/string hooks. JSON decoding itself produces only these exact types.
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
    """Recognize Prometheus instant/range sample pairs: [timestamp, value]."""
    return type(value) is list and len(value) == 2 and _finite_number(value[0]) and _finite_number(value[1])


def _is_metric_map(value: Any) -> bool:
    """Require the label map carried by a Prometheus vector/matrix series."""
    return type(value) is dict and all(type(key) is str and type(label) is str for key, label in value.items())


def _normalize_expected_labels(expected_labels: Mapping[str, str] | None) -> dict[str, str] | None:
    if expected_labels is None:
        return None
    # This is caller-owned configuration rather than upstream MCP material, but avoid
    # invoking extension hooks here as well. Public callers should provide a plain dict.
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
    """Validate one Prometheus vector/matrix series object."""
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
    """Accept only the direct JSON shape of Prometheus vector/matrix model.Value."""
    return type(value) is list and any(_series_has_sample(series, expected_labels) for series in value)


def contains_prometheus_sample(
    value: Any,
    *,
    expected_labels: Mapping[str, str] | None = None,
    depth: int = 0,
) -> bool:
    """Return True only for a qualifying series sample in a Grafana MCP query envelope.

    ``expected_labels`` is an optional exact subset match against each series' metric
    labels. Extra labels are allowed, but every expected key/value must be present on
    the same series that carries the accepted sample. Invalid expected-label types fail
    closed rather than silently disabling binding.

    mcp-grafana v1.4.1 returns ``QueryPrometheusResult`` with ``data``, optional
    ``hints``, and optional ``warnings``. MCP may serialize that object into a text
    content block or expose structured content. Traversal is bounded and restricted to
    known MCP payload-bearing fields; telemetry itself must have the direct
    vector/matrix shape under ``data``. Metadata, annotations, warnings, hints, and
    arbitrary extension fields cannot satisfy the evidence gate. Only exact JSON-like
    built-ins are traversed; extension subclasses fail closed without invoking hooks.
    """
    normalized_labels = _normalize_expected_labels(expected_labels)
    if expected_labels is not None and normalized_labels is None:
        return False
    if depth > MAX_EVIDENCE_NESTING_DEPTH:
        return False

    value_type = type(value)
    if value_type is str:
        decoded = _decode_json_text(value)
        return decoded is not None and contains_prometheus_sample(
            decoded, expected_labels=normalized_labels, depth=depth + 1
        )
    if value_type is list:
        return any(
            contains_prometheus_sample(item, expected_labels=normalized_labels, depth=depth + 1)
            for item in value
        )
    if value_type is not dict:
        return False

    if "data" in value and _data_contains_series_sample(value["data"], normalized_labels):
        return True

    return any(
        contains_prometheus_sample(value[key], expected_labels=normalized_labels, depth=depth + 1)
        for key in _MCP_PAYLOAD_KEYS
        if key in value
    )

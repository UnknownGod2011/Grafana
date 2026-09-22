"""Fail-closed semantic evidence gate for the Grafana MCP release smoke."""
from __future__ import annotations

from typing import Any

from mcp_prometheus_evidence import contains_prometheus_sample
from mcp_smoke_config import SmokeConfigError, expected_labels


class PrometheusEvidenceError(ValueError):
    """Raised when smoke configuration or returned telemetry cannot prove the target series."""


def assert_expected_prometheus_sample(content: Any, raw_expected_labels: str | None) -> dict[str, str]:
    """Validate configured series identity and require a matching finite Prometheus sample.

    Returns the normalized expected-label mapping so callers can report the identity that
    was actually enforced without reparsing configuration.
    """
    try:
        labels = expected_labels(raw_expected_labels)
    except SmokeConfigError as exc:
        raise PrometheusEvidenceError(f"invalid STAGEGUARD_MCP_SMOKE_EXPECTED_LABELS: {exc}") from exc

    if not contains_prometheus_sample(content, expected_labels=labels):
        rendered = ", ".join(f"{key}={value!r}" for key, value in sorted(labels.items()))
        raise PrometheusEvidenceError(
            "query_prometheus returned no genuine Prometheus telemetry sample for "
            f"the configured StageGuard series ({rendered})"
        )
    return labels

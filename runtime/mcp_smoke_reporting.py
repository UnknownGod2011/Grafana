"""Safe, bounded reporting for the production Grafana MCP smoke.

The smoke proves evidence semantics separately. This module deliberately reports only
non-sensitive release metadata; raw PromQL, MCP evidence content, and sample values do
not belong in CI/operator logs.
"""
from __future__ import annotations

from typing import Any

MAX_REPORT_FIELD_CHARS = 128
MAX_EXPECTED_LABELS = 16


class SmokeReportError(ValueError):
    """Raised when supposedly safe release metadata is malformed."""


def _safe_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > MAX_REPORT_FIELD_CHARS:
        raise SmokeReportError(f"{field} must be a non-empty bounded string")
    for char in value:
        codepoint = ord(char)
        if codepoint < 32 or 0x7F <= codepoint <= 0x9F or codepoint in {
            0x2028, 0x2029, 0x202A, 0x202B, 0x202C, 0x202D, 0x202E,
            0x2066, 0x2067, 0x2068, 0x2069,
        }:
            raise SmokeReportError(f"{field} contains unsafe display characters")
    return value


def build_safe_smoke_report(
    *,
    server_info: dict[str, Any],
    protocol_version: str,
    tools: list[str],
    datasource_uid: str,
    expected_series_labels: dict[str, str],
) -> dict[str, Any]:
    """Build an operator-safe success report without raw query/evidence payloads."""
    if not isinstance(server_info, dict):
        raise SmokeReportError("server_info must be an object")
    safe_server = {
        "name": _safe_text(server_info.get("name"), "server_info.name"),
        "version": _safe_text(server_info.get("version"), "server_info.version"),
    }
    if not isinstance(tools, list) or not tools:
        raise SmokeReportError("tools must be a non-empty list")
    safe_tools = sorted({_safe_text(tool, "tool") for tool in tools})
    if not isinstance(expected_series_labels, dict) or not expected_series_labels:
        raise SmokeReportError("expected_series_labels must be a non-empty object")
    if len(expected_series_labels) > MAX_EXPECTED_LABELS:
        raise SmokeReportError("expected_series_labels exceeds report label limit")
    safe_labels = {
        _safe_text(key, "label name"): _safe_text(value, "label value")
        for key, value in expected_series_labels.items()
    }
    return {
        "server": safe_server,
        "protocol_version": _safe_text(protocol_version, "protocol_version"),
        "advertised_read_only_tools": safe_tools,
        "datasource_uid": _safe_text(datasource_uid, "datasource_uid"),
        "expected_series_labels": safe_labels,
        "evidence": "verified",
    }

from __future__ import annotations

import pytest

from mcp_smoke_reporting import SmokeReportError, build_safe_smoke_report


def _report(**overrides):
    values = {
        "server_info": {"name": "mcp-grafana", "version": "1.4.1"},
        "protocol_version": "2025-06-18",
        "tools": ["query_prometheus", "list_datasources"],
        "datasource_uid": "stageguard-prometheus",
        "expected_series_labels": {"production_id": "broadcast-alpha", "uplink": "uplink-b"},
    }
    values.update(overrides)
    return build_safe_smoke_report(**values)


def test_success_report_contains_only_release_metadata() -> None:
    report = _report()
    assert report["evidence"] == "verified"
    assert report["server"] == {"name": "mcp-grafana", "version": "1.4.1"}
    assert report["expected_series_labels"]["uplink"] == "uplink-b"
    assert "query" not in report
    assert "result" not in report
    assert "content" not in report
    assert "sample" not in report


def test_report_rejects_display_spoofing() -> None:
    with pytest.raises(SmokeReportError):
        _report(datasource_uid="stageguard\u202eprometheus")


def test_report_rejects_unbounded_labels() -> None:
    with pytest.raises(SmokeReportError):
        _report(expected_series_labels={f"label_{index}": "x" for index in range(17)})


def test_report_deduplicates_and_sorts_tool_names() -> None:
    report = _report(tools=["query_prometheus", "list_datasources", "query_prometheus"])
    assert report["advertised_read_only_tools"] == ["list_datasources", "query_prometheus"]

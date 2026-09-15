from __future__ import annotations

import pytest

from runtime.mcp_smoke import (
    McpError,
    _assert_initialize_result,
    _assert_read_only_tool_surface,
    _request_timeout_seconds,
    _tool_map,
)


def _read_tool(name: str) -> dict[str, object]:
    return {"name": name, "annotations": {"readOnlyHint": True}}


def _initialize_result(protocol: str = "2025-06-18") -> dict[str, object]:
    return {
        "protocolVersion": protocol,
        "capabilities": {"tools": {}},
        "serverInfo": {"name": "mcp-grafana", "version": "1.4.1"},
    }


def test_initialize_contract_accepts_expected_protocol_and_metadata() -> None:
    _assert_initialize_result(_initialize_result(), "2025-06-18")


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"protocolVersion": None, "capabilities": {}, "serverInfo": {"name": "mcp-grafana", "version": "1.4.1"}},
        {"protocolVersion": "2025-06-18", "capabilities": [], "serverInfo": {"name": "mcp-grafana", "version": "1.4.1"}},
        {"protocolVersion": "2025-06-18", "capabilities": {}, "serverInfo": None},
        {"protocolVersion": "2025-06-18", "capabilities": {}, "serverInfo": {"name": "", "version": "1.4.1"}},
        {"protocolVersion": "2025-06-18", "capabilities": {}, "serverInfo": {"name": "mcp-grafana", "version": ""}},
    ],
)
def test_initialize_contract_rejects_malformed_negotiation(payload: dict[str, object]) -> None:
    with pytest.raises(McpError):
        _assert_initialize_result(payload, "2025-06-18")


def test_initialize_contract_rejects_protocol_downgrade_or_mismatch() -> None:
    with pytest.raises(McpError, match="protocol negotiation mismatch"):
        _assert_initialize_result(_initialize_result("2024-11-05"), "2025-06-18")


def test_tool_map_rejects_duplicate_names() -> None:
    with pytest.raises(McpError, match="duplicate tool name"):
        _tool_map({"tools": [_read_tool("query_prometheus"), _read_tool("query_prometheus")]})


@pytest.mark.parametrize(
    "payload",
    [
        {"tools": {}},
        {"tools": [None]},
        {"tools": [{"name": ""}]},
        {"tools": [{"name": 42}]},
    ],
)
def test_tool_map_rejects_malformed_advertisements(payload: dict[str, object]) -> None:
    with pytest.raises(McpError):
        _tool_map(payload)


def test_read_only_surface_requires_stageguard_evidence_tools() -> None:
    tools = {"list_datasources": _read_tool("list_datasources")}
    with pytest.raises(McpError, match="query_prometheus"):
        _assert_read_only_tool_surface(tools)


def test_read_only_surface_rejects_any_tool_without_explicit_read_only_hint() -> None:
    tools = {
        "list_datasources": _read_tool("list_datasources"),
        "query_prometheus": _read_tool("query_prometheus"),
        "future_tool": {"name": "future_tool", "annotations": {}},
    }
    with pytest.raises(McpError, match="future_tool"):
        _assert_read_only_tool_surface(tools)


def test_read_only_surface_accepts_required_tools_when_explicitly_read_only() -> None:
    tools = {
        "list_datasources": _read_tool("list_datasources"),
        "query_prometheus": _read_tool("query_prometheus"),
    }
    _assert_read_only_tool_surface(tools)


@pytest.mark.parametrize("raw", ["0", "-1", "nan", "inf", "121"])
def test_request_timeout_rejects_unsafe_values(raw: str) -> None:
    with pytest.raises(McpError):
        _request_timeout_seconds(raw)


def test_request_timeout_accepts_bounded_finite_value() -> None:
    assert _request_timeout_seconds("2.5") == 2.5

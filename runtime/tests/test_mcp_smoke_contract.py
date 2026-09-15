from __future__ import annotations

import pytest

from runtime.mcp_smoke import (
    McpError,
    _assert_read_only_tool_surface,
    _request_timeout_seconds,
    _tool_map,
)


def _read_tool(name: str) -> dict[str, object]:
    return {"name": name, "annotations": {"readOnlyHint": True}}


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
        # A future upstream/category expansion must not silently become part of the
        # StageGuard evidence plane merely because its name sounds harmless.
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

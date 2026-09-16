from __future__ import annotations

import pytest

from runtime.mcp_smoke import (
    MAX_DIAGNOSTIC_CHARS,
    MAX_SERVER_INFO_FIELD_CHARS,
    MAX_TOOL_NAME_CHARS,
    McpError,
    _assert_initialize_result,
    _assert_read_only_tool_surface,
    _assert_tool_result,
    _bounded_diagnostic,
    _redacted_command,
    _request_timeout_seconds,
    _tool_map,
)


def _read_tool(name: str) -> dict[str, object]:
    return {"name": name, "annotations": {"readOnlyHint": True}}


def _initialize_result(protocol: str = "2025-06-18") -> dict[str, object]:
    return {"protocolVersion": protocol, "capabilities": {"tools": {}}, "serverInfo": {"name": "mcp-grafana", "version": "1.4.1"}}


def test_initialize_contract_accepts_expected_protocol_and_metadata() -> None:
    _assert_initialize_result(_initialize_result(), "2025-06-18")


@pytest.mark.parametrize("payload", [
    {},
    {"protocolVersion": None, "capabilities": {}, "serverInfo": {"name": "mcp-grafana", "version": "1.4.1"}},
    {"protocolVersion": "2025-06-18", "capabilities": [], "serverInfo": {"name": "mcp-grafana", "version": "1.4.1"}},
    {"protocolVersion": "2025-06-18", "capabilities": {}, "serverInfo": None},
    {"protocolVersion": "2025-06-18", "capabilities": {}, "serverInfo": {"name": "", "version": "1.4.1"}},
    {"protocolVersion": "2025-06-18", "capabilities": {}, "serverInfo": {"name": "mcp-grafana", "version": ""}},
])
def test_initialize_contract_rejects_malformed_negotiation(payload: dict[str, object]) -> None:
    with pytest.raises(McpError):
        _assert_initialize_result(payload, "2025-06-18")


def test_initialize_contract_rejects_protocol_downgrade_or_mismatch() -> None:
    with pytest.raises(McpError, match="protocol negotiation mismatch"):
        _assert_initialize_result(_initialize_result("2024-11-05"), "2025-06-18")


@pytest.mark.parametrize(("field", "value"), [
    ("name", "x" * (MAX_SERVER_INFO_FIELD_CHARS + 1)),
    ("version", "x" * (MAX_SERVER_INFO_FIELD_CHARS + 1)),
    ("name", "mcp-grafana\nforged-log-line"),
    ("version", "1.4.1\x7fhidden"),
    ("name", "mcp-grafana\x85next-line"),
    ("version", "1.4.1\u2028forged"),
    ("name", "mcp-\u202egrafana"),
    ("version", "1.4.1\u2066hidden\u2069"),
])
def test_initialize_contract_rejects_unsafe_server_metadata(field: str, value: str) -> None:
    payload = _initialize_result()
    server_info = payload["serverInfo"]
    assert isinstance(server_info, dict)
    server_info[field] = value
    with pytest.raises(McpError, match=f"serverInfo.{field}"):
        _assert_initialize_result(payload, "2025-06-18")


def test_initialize_contract_accepts_server_metadata_at_bound() -> None:
    payload = _initialize_result()
    server_info = payload["serverInfo"]
    assert isinstance(server_info, dict)
    server_info["name"] = "n" * MAX_SERVER_INFO_FIELD_CHARS
    server_info["version"] = "v" * MAX_SERVER_INFO_FIELD_CHARS
    _assert_initialize_result(payload, "2025-06-18")


def test_initialize_contract_accepts_printable_unicode_metadata() -> None:
    payload = _initialize_result()
    server_info = payload["serverInfo"]
    assert isinstance(server_info, dict)
    server_info["name"] = "mcp-grafana-東京"
    _assert_initialize_result(payload, "2025-06-18")


def test_tool_map_rejects_duplicate_names() -> None:
    with pytest.raises(McpError, match="duplicate tool name"):
        _tool_map({"tools": [_read_tool("query_prometheus"), _read_tool("query_prometheus")]})


@pytest.mark.parametrize("payload", [{"tools": {}}, {"tools": [None]}, {"tools": [{"name": ""}]}, {"tools": [{"name": 42}]}])
def test_tool_map_rejects_malformed_advertisements(payload: dict[str, object]) -> None:
    with pytest.raises(McpError):
        _tool_map(payload)


@pytest.mark.parametrize("name", [
    "x" * (MAX_TOOL_NAME_CHARS + 1),
    "query_prometheus\nforged-log-line",
    "list_datasources\x7fhidden",
    "query_prometheus\x85next-line",
    "query_prometheus\u2029forged",
    "query_\u202eprometheus",
    "query_\u2067prometheus\u2069",
])
def test_tool_map_rejects_unsafe_names(name: str) -> None:
    with pytest.raises(McpError, match="unsafe name"):
        _tool_map({"tools": [_read_tool(name)]})


def test_tool_map_accepts_name_at_bound() -> None:
    name = "t" * MAX_TOOL_NAME_CHARS
    assert list(_tool_map({"tools": [_read_tool(name)]})) == [name]


def test_tool_map_accepts_printable_unicode_name() -> None:
    name = "query_prometheus_東京"
    assert list(_tool_map({"tools": [_read_tool(name)]})) == [name]


def test_read_only_surface_requires_stageguard_evidence_tools() -> None:
    tools = {"list_datasources": _read_tool("list_datasources")}
    with pytest.raises(McpError, match="query_prometheus"):
        _assert_read_only_tool_surface(tools)


def test_read_only_surface_rejects_any_tool_without_explicit_read_only_hint() -> None:
    tools = {"list_datasources": _read_tool("list_datasources"), "query_prometheus": _read_tool("query_prometheus"), "future_tool": {"name": "future_tool", "annotations": {}}}
    with pytest.raises(McpError, match="future_tool"):
        _assert_read_only_tool_surface(tools)


def test_read_only_surface_accepts_required_tools_when_explicitly_read_only() -> None:
    tools = {"list_datasources": _read_tool("list_datasources"), "query_prometheus": _read_tool("query_prometheus")}
    _assert_read_only_tool_surface(tools)


@pytest.mark.parametrize("raw", ["0", "-1", "nan", "inf", "121"])
def test_request_timeout_rejects_unsafe_values(raw: str) -> None:
    with pytest.raises(McpError):
        _request_timeout_seconds(raw)


def test_request_timeout_accepts_bounded_finite_value() -> None:
    assert _request_timeout_seconds("2.5") == 2.5


def test_bounded_diagnostic_preserves_small_payload_and_escapes_controls() -> None:
    rendered = _bounded_diagnostic({"message": "bad\nforged"})
    assert "bad\\nforged" in rendered
    assert "\n" not in rendered
    assert "truncated" not in rendered


def test_bounded_diagnostic_truncates_large_peer_payload() -> None:
    rendered = _bounded_diagnostic("x" * (MAX_DIAGNOSTIC_CHARS * 2))
    assert len(rendered) < MAX_DIAGNOSTIC_CHARS + 100
    assert "<truncated " in rendered


def test_tool_error_diagnostic_is_bounded() -> None:
    with pytest.raises(McpError) as captured:
        _assert_tool_result("query_prometheus", {"isError": True, "content": "x" * (MAX_DIAGNOSTIC_CHARS * 4)})
    assert len(str(captured.value)) < MAX_DIAGNOSTIC_CHARS + 200
    assert "<truncated " in str(captured.value)


def test_redacted_command_hides_inline_secret_values() -> None:
    rendered = _redacted_command(["docker", "run", "--api-key", "super-secret", "--token=abc123", "mcp"])
    assert "super-secret" not in rendered
    assert "abc123" not in rendered
    assert "<redacted>" in rendered
    assert "docker run" in rendered


def test_redacted_command_preserves_non_sensitive_arguments() -> None:
    rendered = _redacted_command(["docker", "compose", "run", "--rm", "-T", "mcp"])
    assert rendered == "docker compose run --rm -T mcp"

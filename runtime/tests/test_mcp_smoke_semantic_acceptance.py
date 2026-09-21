from __future__ import annotations

import pytest

from runtime.mcp_smoke import McpError, _assert_tool_result


def test_successful_tool_call_without_content_is_not_accepted_as_evidence() -> None:
    """A JSON-RPC success envelope alone must not make the evidence smoke green."""
    with pytest.raises(McpError, match="content"):
        _assert_tool_result("query_prometheus", {"isError": False})


def test_successful_tool_call_with_empty_content_is_not_accepted_as_evidence() -> None:
    """An empty MCP content array cannot prove that Grafana returned telemetry."""
    with pytest.raises(McpError, match="content"):
        _assert_tool_result("query_prometheus", {"isError": False, "content": []})


def test_successful_tool_call_with_text_content_remains_acceptable() -> None:
    _assert_tool_result(
        "query_prometheus",
        {
            "isError": False,
            "content": [
                {
                    "type": "text",
                    "text": '[{"metric":{"production_id":"broadcast-alpha","uplink":"uplink-b"},"value":[1,"0.2"]}]',
                }
            ],
        },
    )

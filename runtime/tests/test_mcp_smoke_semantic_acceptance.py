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


@pytest.mark.parametrize(
    "content",
    [
        [{}],
        [{"type": "text"}],
        [{"type": "text", "text": ""}],
        [{"type": "text", "text": "   "}],
        [{"type": "text", "annotations": {"audience": ["assistant"]}}],
        [{"type": "resource", "resource": {}}],
        [{"type": "resource", "resource": {"uri": "   "}}],
        [{"type": "resource", "resource": {"contents": []}}],
        [{"type": "resource", "resource": {"contents": [{"text": ""}]}}],
        [{"type": "resource", "resource": {"ok": True}}],
        [{"type": "resource", "resource": {"cached": False}}],
        [{"type": "resource", "resource": {"annotations": {"audience": ["assistant"]}}}],
        [{"type": "resource", "resource": {"meta": {"source": "grafana"}}}],
        [{"type": "resource", "resource": {"_meta": {"trace": "present"}}}],
        ["not-an-mcp-content-object"],
    ],
)
def test_metadata_only_or_blank_content_is_not_accepted_as_evidence(content: list[object]) -> None:
    """Content metadata or structurally non-empty containers without payload must fail closed."""
    with pytest.raises(McpError, match="content"):
        _assert_tool_result("query_prometheus", {"isError": False, "content": content})


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


def test_non_text_content_with_nonempty_payload_remains_format_tolerant() -> None:
    """Do not couple the smoke to one upstream serialization before the live 1.4.1 gate."""
    _assert_tool_result(
        "query_prometheus",
        {"isError": False, "content": [{"type": "resource", "resource": {"uri": "stageguard://evidence/1"}}]},
    )


def test_nested_resource_with_actual_text_payload_remains_acceptable() -> None:
    _assert_tool_result(
        "query_prometheus",
        {
            "isError": False,
            "content": [
                {
                    "type": "resource",
                    "resource": {
                        "contents": [
                            {"text": '[{"metric":{"production_id":"broadcast-alpha"},"value":[1,"0.2"]}]'}
                        ]
                    },
                }
            ],
        },
    )


def test_finite_numeric_sample_remains_acceptable() -> None:
    """A numeric zero is valid telemetry and must not be confused with an empty value."""
    _assert_tool_result(
        "query_prometheus",
        {"isError": False, "content": [{"type": "resource", "resource": {"sample": 0}}]},
    )

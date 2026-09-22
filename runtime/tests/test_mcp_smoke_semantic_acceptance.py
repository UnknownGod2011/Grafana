from __future__ import annotations

import pytest

from runtime.mcp_smoke import McpError, _assert_datasource_present, _assert_tool_result


def test_successful_tool_call_without_content_is_not_accepted_as_evidence() -> None:
    with pytest.raises(McpError, match="content"):
        _assert_tool_result("query_prometheus", {"isError": False})


def test_successful_tool_call_with_empty_content_is_not_accepted_as_evidence() -> None:
    with pytest.raises(McpError, match="content"):
        _assert_tool_result("query_prometheus", {"isError": False, "content": []})


@pytest.mark.parametrize(
    "content",
    [
        [{}], [{"type": "text"}], [{"type": "text", "text": ""}], [{"type": "text", "text": "   "}],
        [{"type": "text", "annotations": {"audience": ["assistant"]}}], [{"type": "resource", "resource": {}}],
        [{"type": "resource", "resource": {"uri": "   "}}], [{"type": "resource", "resource": {"contents": []}}],
        [{"type": "resource", "resource": {"contents": [{"text": ""}]}}], [{"type": "resource", "resource": {"ok": True}}],
        [{"type": "resource", "resource": {"cached": False}}], [{"type": "resource", "resource": {"annotations": {"audience": ["assistant"]}}}],
        [{"type": "resource", "resource": {"meta": {"source": "grafana"}}}], [{"type": "resource", "resource": {"_meta": {"trace": "present"}}}],
        ["not-an-mcp-content-object"],
    ],
)
def test_metadata_only_or_blank_content_is_not_accepted_as_evidence(content: list[object]) -> None:
    with pytest.raises(McpError, match="content"):
        _assert_tool_result("query_prometheus", {"isError": False, "content": content})


def test_successful_tool_call_with_text_content_remains_acceptable() -> None:
    _assert_tool_result("query_prometheus", {"isError": False, "content": [{"type": "text", "text": '[{"metric":{"production_id":"broadcast-alpha","uplink":"uplink-b"},"value":[1,"0.2"]}]'}]})


def test_non_text_content_with_nonempty_payload_remains_format_tolerant() -> None:
    _assert_tool_result("query_prometheus", {"isError": False, "content": [{"type": "resource", "resource": {"uri": "stageguard://evidence/1"}}]})


def test_nested_resource_with_actual_text_payload_remains_acceptable() -> None:
    _assert_tool_result("query_prometheus", {"isError": False, "content": [{"type": "resource", "resource": {"contents": [{"text": '[{"metric":{"production_id":"broadcast-alpha"},"value":[1,"0.2"]}]'}]}}]})


def test_finite_numeric_sample_remains_acceptable() -> None:
    _assert_tool_result("query_prometheus", {"isError": False, "content": [{"type": "resource", "resource": {"sample": 0}}]})


def test_datasource_acceptance_requires_exact_configured_uid() -> None:
    result = {"isError": False, "content": [{"type": "text", "text": '{"datasources":[{"uid":"other-prometheus","name":"Other","type":"prometheus"}],"total":1,"hasMore":false}'}]}
    with pytest.raises(McpError, match="configured datasource UID"):
        _assert_datasource_present(result, "stageguard-prometheus")


def test_datasource_acceptance_rejects_uid_as_substring_only() -> None:
    result = {"isError": False, "content": [{"type": "text", "text": '{"datasources":[{"uid":"stageguard-prometheus-copy","name":"Copy","type":"prometheus"}],"total":1,"hasMore":false}'}]}
    with pytest.raises(McpError, match="configured datasource UID"):
        _assert_datasource_present(result, "stageguard-prometheus")


def test_datasource_acceptance_does_not_confuse_name_with_uid() -> None:
    result = {"isError": False, "content": [{"type": "text", "text": '{"datasources":[{"uid":"other-prometheus","name":"stageguard-prometheus","type":"prometheus"}],"total":1,"hasMore":false}'}]}
    with pytest.raises(McpError, match="configured datasource UID"):
        _assert_datasource_present(result, "stageguard-prometheus")


def test_datasource_acceptance_decodes_official_structured_json_text() -> None:
    result = {"isError": False, "content": [{"type": "text", "text": '{"datasources":[{"id":1,"uid":"stageguard-prometheus","name":"StageGuard Prometheus","type":"prometheus","isDefault":true}],"total":1,"hasMore":false}'}]}
    _assert_datasource_present(result, "stageguard-prometheus")


def test_datasource_acceptance_supports_structured_content_without_text_coupling() -> None:
    result = {"isError": False, "content": [{"type": "resource", "resource": {"datasources": [{"uid": "stageguard-prometheus", "type": "prometheus"}]}}]}
    _assert_datasource_present(result, "stageguard-prometheus")

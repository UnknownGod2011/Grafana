from __future__ import annotations

from runtime.mcp_datasource_identity import contains_datasource_uid


def test_matches_uid_field_in_official_style_json_text() -> None:
    payload = '{"datasources":[{"id":1,"uid":"stageguard-prometheus","name":"StageGuard Prometheus","type":"prometheus"}],"total":1}'
    assert contains_datasource_uid(payload, "stageguard-prometheus")


def test_rejects_name_equal_to_expected_uid() -> None:
    payload = '{"datasources":[{"uid":"other-prometheus","name":"stageguard-prometheus","type":"prometheus"}]}'
    assert not contains_datasource_uid(payload, "stageguard-prometheus")


def test_rejects_plain_string_equal_to_expected_uid() -> None:
    assert not contains_datasource_uid("stageguard-prometheus", "stageguard-prometheus")


def test_rejects_uid_substring_collision() -> None:
    payload = {"datasources": [{"uid": "stageguard-prometheus-copy"}]}
    assert not contains_datasource_uid(payload, "stageguard-prometheus")


def test_supports_structured_mcp_content() -> None:
    payload = [{"type": "resource", "resource": {"datasources": [{"uid": "stageguard-prometheus"}]}}]
    assert contains_datasource_uid(payload, "stageguard-prometheus")


def test_does_not_accept_uid_key_with_non_string_value() -> None:
    assert not contains_datasource_uid({"uid": 123}, "123")


def test_nested_uid_is_found_without_using_other_fields_as_identity() -> None:
    payload = {"wrapper": {"name": "stageguard-prometheus", "items": [{"uid": "stageguard-prometheus"}]}}
    assert contains_datasource_uid(payload, "stageguard-prometheus")


def test_traversal_is_bounded() -> None:
    payload: object = {"uid": "stageguard-prometheus"}
    for _ in range(18):
        payload = {"nested": payload}
    assert not contains_datasource_uid(payload, "stageguard-prometheus")

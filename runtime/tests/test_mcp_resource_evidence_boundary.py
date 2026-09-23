from __future__ import annotations

from runtime.mcp_prometheus_evidence import contains_prometheus_sample


def test_accepts_json_query_result_in_standard_embedded_resource_text() -> None:
    payload = [{
        "type": "resource",
        "resource": {
            "uri": "stageguard://prometheus/result",
            "mimeType": "application/json",
            "text": '{"data":[{"metric":{"production_id":"broadcast-alpha"},"value":[1789990000,"0.2"]}]}',
        },
    }]
    assert contains_prometheus_sample(payload, expected_labels={"production_id": "broadcast-alpha"})


def test_rejects_data_extension_inside_standard_embedded_resource() -> None:
    payload = [{
        "type": "resource",
        "resource": {
            "uri": "stageguard://status",
            "text": "operational status, not query evidence",
            "data": [{"metric": {"production_id": "broadcast-alpha"}, "value": [1789990000, "99"]}],
        },
    }]
    assert not contains_prometheus_sample(payload, expected_labels={"production_id": "broadcast-alpha"})


def test_rejects_data_extension_inside_blob_resource() -> None:
    payload = [{
        "type": "resource",
        "resource": {
            "uri": "stageguard://capture",
            "mimeType": "application/octet-stream",
            "blob": "AAEC",
            "data": [{"metric": {"uplink": "uplink-b"}, "value": [1789990000, "99"]}],
        },
    }]
    assert not contains_prometheus_sample(payload, expected_labels={"uplink": "uplink-b"})


def test_resource_link_cannot_smuggle_query_evidence() -> None:
    payload = [{
        "type": "resource_link",
        "uri": "stageguard://status",
        "data": [{"metric": {}, "value": [1789990000, "99"]}],
    }]
    assert not contains_prometheus_sample(payload)

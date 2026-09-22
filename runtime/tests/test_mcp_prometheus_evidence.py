from __future__ import annotations

from runtime.mcp_prometheus_evidence import contains_prometheus_sample


def test_accepts_official_style_instant_vector_json_text() -> None:
    payload = '[{"metric":{"production_id":"broadcast-alpha"},"value":[1789990000.25,"0.2"]}]'
    assert contains_prometheus_sample(payload)


def test_accepts_range_vector_samples() -> None:
    payload = {"data": {"result": [{"metric": {"uplink": "uplink-b"}, "values": [[1789990000, "0"], [1789990015, "0.4"]]}]}}
    assert contains_prometheus_sample(payload)


def test_zero_sample_is_valid_evidence() -> None:
    assert contains_prometheus_sample({"value": [1789990000, "0"]})


def test_rejects_metric_metadata_without_sample() -> None:
    assert not contains_prometheus_sample({"metric": {"production_id": "broadcast-alpha", "uplink": "uplink-b"}})


def test_rejects_empty_prometheus_result() -> None:
    assert not contains_prometheus_sample('{"status":"success","data":{"resultType":"vector","result":[]}}')


def test_rejects_arbitrary_numeric_pair_not_bound_to_sample_field() -> None:
    assert not contains_prometheus_sample({"bounds": [1789990000, 0.2]})


def test_rejects_non_finite_sample_values() -> None:
    assert not contains_prometheus_sample({"value": [1789990000, "NaN"]})
    assert not contains_prometheus_sample({"value": [1789990000, "Inf"]})


def test_rejects_boolean_lookalikes() -> None:
    assert not contains_prometheus_sample({"value": [True, False]})


def test_supports_structured_mcp_content() -> None:
    payload = [{"type": "resource", "resource": {"data": {"result": [{"value": [1789990000, "1.25"]}]}}}]
    assert contains_prometheus_sample(payload)


def test_depth_limit_fails_closed() -> None:
    payload: object = {"value": [1789990000, "0.2"]}
    for _ in range(18):
        payload = {"nested": payload}
    assert not contains_prometheus_sample(payload)

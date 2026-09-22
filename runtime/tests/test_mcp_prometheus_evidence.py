from __future__ import annotations

from runtime.mcp_prometheus_evidence import contains_prometheus_sample


def test_accepts_pinned_mcp_grafana_instant_vector_shape() -> None:
    # mcp-grafana v1.4.1 QueryPrometheusResult serializes model.Value under `data`.
    payload = '{"data":[{"metric":{"production_id":"broadcast-alpha"},"value":[1789990000.25,"0.2"]}],"warnings":[]}'
    assert contains_prometheus_sample(payload)


def test_accepts_range_vector_samples_under_data() -> None:
    payload = {"data": [{"metric": {"uplink": "uplink-b"}, "values": [[1789990000, "0"], [1789990015, "0.4"]]}]}
    assert contains_prometheus_sample(payload)


def test_zero_sample_is_valid_evidence() -> None:
    assert contains_prometheus_sample({"data": [{"metric": {}, "value": [1789990000, "0"]}]})


def test_rejects_metric_metadata_without_sample() -> None:
    assert not contains_prometheus_sample({"data": [{"metric": {"production_id": "broadcast-alpha", "uplink": "uplink-b"}}]})


def test_rejects_empty_official_result() -> None:
    assert not contains_prometheus_sample('{"data":[],"hints":{"reason":"empty"},"warnings":[]}')


def test_rejects_arbitrary_numeric_pair_not_bound_to_sample_field() -> None:
    assert not contains_prometheus_sample({"data": {"bounds": [1789990000, 0.2]}})


def test_rejects_sample_field_without_metric_series_identity() -> None:
    assert not contains_prometheus_sample({"data": [{"value": [1789990000, "0.2"]}]})


def test_rejects_nested_sample_lookalike_under_data() -> None:
    payload = {"data": {"metadata": {"value": [1789990000, "0.2"]}}}
    assert not contains_prometheus_sample(payload)


def test_rejects_nested_series_shaped_lookalike_under_data() -> None:
    # QueryPrometheusResult.Data is model.Value. Vector/matrix JSON is a direct list;
    # a nested series-shaped object is not a shape the pinned upstream contract emits.
    payload = {"data": {"metadata": [{"metric": {}, "value": [1789990000, "0.2"]}]}}
    assert not contains_prometheus_sample(payload)


def test_rejects_non_string_metric_labels() -> None:
    payload = {"data": [{"metric": {"production_id": 7}, "value": [1789990000, "0.2"]}]}
    assert not contains_prometheus_sample(payload)


def test_rejects_prometheus_scalar_as_stageguard_series_evidence() -> None:
    # prometheus/common/model.Value can also be a Scalar, encoded as a sample pair.
    # StageGuard probes a named metric series, so scalar output must fail closed.
    assert not contains_prometheus_sample({"data": [1789990000, "0.2"]})


def test_rejects_non_finite_sample_values() -> None:
    assert not contains_prometheus_sample({"data": [{"metric": {}, "value": [1789990000, "NaN"]}]})
    assert not contains_prometheus_sample({"data": [{"metric": {}, "value": [1789990000, "Inf"]}]})


def test_rejects_boolean_lookalikes() -> None:
    assert not contains_prometheus_sample({"data": [{"metric": {}, "value": [True, False]}]})


def test_supports_structured_mcp_content() -> None:
    payload = [{"type": "resource", "resource": {"data": [{"metric": {}, "value": [1789990000, "1.25"]}]}}]
    assert contains_prometheus_sample(payload)


def test_rejects_sample_lookalike_in_hints() -> None:
    payload = {"data": [], "hints": {"metric": {}, "value": [1789990000, "99"]}}
    assert not contains_prometheus_sample(payload)


def test_rejects_sample_lookalike_in_warnings() -> None:
    payload = {"data": [], "warnings": [{"metric": {}, "values": [[1789990000, "99"]]}]}
    assert not contains_prometheus_sample(payload)


def test_rejects_bare_sample_without_query_result_data_envelope() -> None:
    assert not contains_prometheus_sample({"metric": {}, "value": [1789990000, "0.2"]})


def test_depth_limit_fails_closed() -> None:
    payload: object = {"data": [{"metric": {}, "value": [1789990000, "0.2"]}]}
    for _ in range(18):
        payload = {"nested": payload}
    assert not contains_prometheus_sample(payload)

from __future__ import annotations

from runtime.mcp_prometheus_evidence import contains_prometheus_sample


def test_accepts_pinned_mcp_grafana_instant_vector_shape() -> None:
    payload = '{"data":[{"metric":{"production_id":"broadcast-alpha"},"value":[1789990000.25,"0.2"]}],"warnings":[]}'
    assert contains_prometheus_sample(payload)


def test_accepts_range_vector_samples_under_data() -> None:
    payload = {"data": [{"metric": {"uplink": "uplink-b"}, "values": [[1789990000, "0"], [1789990015, "0.4"]]}]}
    assert contains_prometheus_sample(payload)


def test_zero_sample_is_valid_evidence() -> None:
    assert contains_prometheus_sample({"data": [{"metric": {}, "value": [1789990000, "0"]}]})


def test_expected_labels_bind_evidence_to_requested_series() -> None:
    payload = {"data": [{"metric": {"production_id": "broadcast-beta", "uplink": "uplink-b"}, "value": [1789990000, "9"]}, {"metric": {"production_id": "broadcast-alpha", "uplink": "uplink-b", "region": "west"}, "value": [1789990000, "0.2"]}]}
    assert contains_prometheus_sample(payload, expected_labels={"production_id": "broadcast-alpha", "uplink": "uplink-b"})


def test_expected_labels_reject_unrelated_series_even_with_valid_sample() -> None:
    payload = {"data": [{"metric": {"production_id": "broadcast-beta", "uplink": "uplink-b"}, "value": [1789990000, "0.2"]}]}
    assert not contains_prometheus_sample(payload, expected_labels={"production_id": "broadcast-alpha", "uplink": "uplink-b"})


def test_expected_labels_must_match_same_series_that_has_sample() -> None:
    payload = {"data": [{"metric": {"production_id": "broadcast-alpha", "uplink": "uplink-b"}}, {"metric": {"production_id": "broadcast-beta", "uplink": "uplink-b"}, "value": [1789990000, "0.2"]}]}
    assert not contains_prometheus_sample(payload, expected_labels={"production_id": "broadcast-alpha", "uplink": "uplink-b"})


def test_invalid_expected_label_types_fail_closed() -> None:
    payload = {"data": [{"metric": {"production_id": "broadcast-alpha"}, "value": [1789990000, "0.2"]}]}
    assert not contains_prometheus_sample(payload, expected_labels={"production_id": 7})  # type: ignore[dict-item]


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
    payload = {"data": {"metadata": [{"metric": {}, "value": [1789990000, "0.2"]}]}}
    assert not contains_prometheus_sample(payload)


def test_rejects_non_string_metric_labels() -> None:
    payload = {"data": [{"metric": {"production_id": 7}, "value": [1789990000, "0.2"]}]}
    assert not contains_prometheus_sample(payload)


def test_rejects_prometheus_scalar_as_stageguard_series_evidence() -> None:
    assert not contains_prometheus_sample({"data": [1789990000, "0.2"]})


def test_rejects_non_finite_sample_values() -> None:
    assert not contains_prometheus_sample({"data": [{"metric": {}, "value": [1789990000, "NaN"]}]})
    assert not contains_prometheus_sample({"data": [{"metric": {}, "value": [1789990000, "Inf"]}]})


def test_rejects_boolean_lookalikes() -> None:
    assert not contains_prometheus_sample({"data": [{"metric": {}, "value": [True, False]}]})


def test_supports_structured_mcp_content() -> None:
    payload = [{"type": "resource", "resource": {"data": [{"metric": {}, "value": [1789990000, "1.25"]}]}}]
    assert contains_prometheus_sample(payload)


def test_supports_text_mcp_content() -> None:
    payload = [{"type": "text", "text": '{"data":[{"metric":{"production_id":"broadcast-alpha"},"value":[1789990000,"0.2"]}]}'}]
    assert contains_prometheus_sample(payload, expected_labels={"production_id": "broadcast-alpha"})


def test_supports_structured_content_envelope() -> None:
    payload = {"structuredContent": {"data": [{"metric": {"uplink": "uplink-b"}, "value": [1789990000, "0.2"]}]}}
    assert contains_prometheus_sample(payload, expected_labels={"uplink": "uplink-b"})


def test_rejects_sample_lookalike_in_hints() -> None:
    payload = {"data": [], "hints": {"metric": {}, "value": [1789990000, "99"]}}
    assert not contains_prometheus_sample(payload)


def test_rejects_sample_lookalike_in_warnings() -> None:
    payload = {"data": [], "warnings": [{"metric": {}, "values": [[1789990000, "99"]]}]}
    assert not contains_prometheus_sample(payload)


def test_rejects_full_query_result_spoof_nested_in_warning() -> None:
    payload = {"data": [], "warnings": [{"data": [{"metric": {"production_id": "broadcast-alpha"}, "value": [1789990000, "99"]}]}]}
    assert not contains_prometheus_sample(payload, expected_labels={"production_id": "broadcast-alpha"})


def test_rejects_full_query_result_spoof_nested_in_annotations() -> None:
    payload = {"type": "text", "text": "not-json operational message", "annotations": {"data": [{"metric": {"uplink": "uplink-b"}, "value": [1789990000, "99"]}]}}
    assert not contains_prometheus_sample(payload, expected_labels={"uplink": "uplink-b"})


def test_rejects_full_query_result_spoof_in_arbitrary_extension_field() -> None:
    payload = {"vendorExtension": {"data": [{"metric": {}, "value": [1789990000, "99"]}]}}
    assert not contains_prometheus_sample(payload)


def test_rejects_bare_sample_without_query_result_data_envelope() -> None:
    assert not contains_prometheus_sample({"metric": {}, "value": [1789990000, "0.2"]})


def test_depth_limit_fails_closed() -> None:
    payload: object = {"data": [{"metric": {}, "value": [1789990000, "0.2"]}]}
    for _ in range(18):
        payload = {"content": payload}
    assert not contains_prometheus_sample(payload)


def test_hostile_dict_subclass_is_opaque_without_hooks() -> None:
    class HostileDict(dict):
        def items(self):
            raise AssertionError("must not inspect extension dict")
        def __contains__(self, key: object) -> bool:
            raise AssertionError("must not inspect extension dict")
        def __getitem__(self, key: object):
            raise AssertionError("must not inspect extension dict")

    assert not contains_prometheus_sample(HostileDict({"data": [{"metric": {}, "value": [1, "1"]}]}))


def test_hostile_list_subclass_is_opaque_without_hooks() -> None:
    class HostileList(list):
        def __iter__(self):
            raise AssertionError("must not iterate extension list")
        def __len__(self):
            raise AssertionError("must not size extension list")
        def __getitem__(self, key: object):
            raise AssertionError("must not index extension list")

    assert not contains_prometheus_sample({"data": HostileList([{"metric": {}, "value": [1, "1"]}])})


def test_hostile_string_subclass_is_opaque_without_hooks() -> None:
    class HostileString(str):
        def strip(self, *args: object, **kwargs: object):
            raise AssertionError("must not strip extension string")
        def __str__(self) -> str:
            raise AssertionError("must not stringify extension string")

    assert not contains_prometheus_sample(HostileString('{"data":[{"metric":{},"value":[1,"1"]}]}'))


def test_expected_labels_extension_mapping_fails_closed_without_hooks() -> None:
    class HostileLabels(dict):
        def items(self):
            raise AssertionError("must not inspect extension labels")

    payload = {"data": [{"metric": {"production_id": "broadcast-alpha"}, "value": [1789990000, "1"]}]}
    assert not contains_prometheus_sample(payload, expected_labels=HostileLabels({"production_id": "broadcast-alpha"}))

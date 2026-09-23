from __future__ import annotations

from runtime.mcp_prometheus_evidence import (
    MAX_LABELS_PER_SERIES,
    MAX_MCP_COLLECTION_ITEMS,
    MAX_PROMETHEUS_SERIES,
    MAX_SAMPLES_PER_SERIES,
    contains_prometheus_sample,
)


def _series(*, metric: dict[str, str] | None = None) -> dict[str, object]:
    return {"metric": metric or {}, "value": [1789990000, "1"]}


def test_rejects_oversized_mcp_content_collection_even_if_first_item_is_valid() -> None:
    valid = {"type": "text", "text": '{"data":[{"metric":{},"value":[1789990000,"1"]}]}' }
    payload = [valid] + [{"type": "text", "text": "status"}] * MAX_MCP_COLLECTION_ITEMS
    assert len(payload) == MAX_MCP_COLLECTION_ITEMS + 1
    assert not contains_prometheus_sample(payload)


def test_accepts_mcp_content_collection_at_limit() -> None:
    payload = [{"type": "text", "text": "status"}] * (MAX_MCP_COLLECTION_ITEMS - 1)
    payload.append({"type": "text", "text": '{"data":[{"metric":{},"value":[1789990000,"1"]}]}'})
    assert contains_prometheus_sample(payload)


def test_rejects_oversized_series_collection_even_if_first_series_is_valid() -> None:
    payload = {"data": [_series()] + [{"metric": {}}] * MAX_PROMETHEUS_SERIES}
    assert len(payload["data"]) == MAX_PROMETHEUS_SERIES + 1
    assert not contains_prometheus_sample(payload)


def test_accepts_series_collection_at_limit() -> None:
    payload = {"data": [{"metric": {}}] * (MAX_PROMETHEUS_SERIES - 1) + [_series()]}
    assert contains_prometheus_sample(payload)


def test_rejects_oversized_sample_collection_even_if_first_sample_is_valid() -> None:
    samples = [[1789990000, "1"]] + [[1789990001, "1"]] * MAX_SAMPLES_PER_SERIES
    payload = {"data": [{"metric": {}, "values": samples}]}
    assert len(samples) == MAX_SAMPLES_PER_SERIES + 1
    assert not contains_prometheus_sample(payload)


def test_accepts_sample_collection_at_limit() -> None:
    samples = [[1789990000 + offset, "1"] for offset in range(MAX_SAMPLES_PER_SERIES)]
    assert contains_prometheus_sample({"data": [{"metric": {}, "values": samples}]})


def test_rejects_oversized_metric_label_map_even_with_valid_sample() -> None:
    metric = {f"label_{index}": "value" for index in range(MAX_LABELS_PER_SERIES + 1)}
    assert not contains_prometheus_sample({"data": [_series(metric=metric)]})


def test_accepts_metric_label_map_at_limit() -> None:
    metric = {f"label_{index}": "value" for index in range(MAX_LABELS_PER_SERIES)}
    assert contains_prometheus_sample({"data": [_series(metric=metric)]})


def test_rejects_oversized_expected_label_map_before_matching() -> None:
    expected = {f"label_{index}": "value" for index in range(MAX_LABELS_PER_SERIES + 1)}
    assert not contains_prometheus_sample({"data": [_series()]}, expected_labels=expected)

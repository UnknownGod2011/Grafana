from __future__ import annotations

import json

import pytest

from mcp_smoke_gate import PrometheusEvidenceError, assert_expected_prometheus_sample


def _content(metric: dict[str, str]) -> list[dict[str, str]]:
    payload = {"data": [{"metric": metric, "value": [1789990000.0, "0.25"]}]}
    return [{"type": "text", "text": json.dumps(payload)}]


def test_default_identity_accepts_matching_stageguard_series() -> None:
    labels = assert_expected_prometheus_sample(
        _content({"production_id": "broadcast-alpha", "uplink": "uplink-b", "region": "local"}),
        None,
    )
    assert labels == {"production_id": "broadcast-alpha", "uplink": "uplink-b"}


def test_unrelated_valid_series_fails_closed() -> None:
    with pytest.raises(PrometheusEvidenceError, match="configured StageGuard series"):
        assert_expected_prometheus_sample(
            _content({"production_id": "broadcast-beta", "uplink": "uplink-b"}),
            None,
        )


def test_custom_identity_is_enforced() -> None:
    raw = json.dumps({"production_id": "show-42", "uplink": "sat-a"})
    labels = assert_expected_prometheus_sample(
        _content({"production_id": "show-42", "uplink": "sat-a", "instance": "edge-1"}),
        raw,
    )
    assert labels == {"production_id": "show-42", "uplink": "sat-a"}


def test_invalid_configuration_is_translated_to_gate_error() -> None:
    with pytest.raises(PrometheusEvidenceError, match="STAGEGUARD_MCP_SMOKE_EXPECTED_LABELS"):
        assert_expected_prometheus_sample(_content({}), "[]")

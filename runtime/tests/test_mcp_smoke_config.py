from __future__ import annotations

import json

import pytest

from mcp_smoke_config import (
    DEFAULT_EXPECTED_LABELS,
    MAX_EXPECTED_LABELS,
    MAX_EXPECTED_LABELS_JSON_CHARS,
    SmokeConfigError,
    expected_labels,
)


def test_unset_expected_labels_use_stageguard_demo_identity() -> None:
    assert expected_labels(None) == DEFAULT_EXPECTED_LABELS
    assert expected_labels("   ") == DEFAULT_EXPECTED_LABELS


def test_custom_expected_labels_are_parsed() -> None:
    assert expected_labels('{"production_id":"prod-7","uplink":"primary","region":"mum"}') == {
        "production_id": "prod-7",
        "uplink": "primary",
        "region": "mum",
    }


def test_printable_unicode_label_value_is_allowed() -> None:
    assert expected_labels(json.dumps({"production_id": "मुंबई"})) == {
        "production_id": "मुंबई"
    }


@pytest.mark.parametrize("raw", ["[]", "null", '"labels"', "{}"])
def test_expected_labels_require_nonempty_object(raw: str) -> None:
    with pytest.raises(SmokeConfigError):
        expected_labels(raw)


def test_expected_labels_reject_invalid_json() -> None:
    with pytest.raises(SmokeConfigError):
        expected_labels("{not-json}")


def test_expected_labels_reject_non_string_values() -> None:
    with pytest.raises(SmokeConfigError):
        expected_labels('{"production_id":7}')


def test_expected_labels_reject_control_characters() -> None:
    with pytest.raises(SmokeConfigError):
        expected_labels(json.dumps({"production_id": "prod\nother"}))


@pytest.mark.parametrize("unsafe", ["\u2028", "\u202e", "\u2066", "\u0085"])
def test_expected_labels_reject_unicode_log_spoofing_characters(unsafe: str) -> None:
    with pytest.raises(SmokeConfigError):
        expected_labels(json.dumps({"production_id": f"prod{unsafe}other"}))


def test_expected_labels_reject_unsafe_label_name() -> None:
    with pytest.raises(SmokeConfigError):
        expected_labels(json.dumps({"production\u202eid": "prod"}))


def test_expected_labels_reject_too_many_labels() -> None:
    raw = json.dumps({f"label_{index}": "value" for index in range(MAX_EXPECTED_LABELS + 1)})
    with pytest.raises(SmokeConfigError):
        expected_labels(raw)


def test_expected_labels_reject_oversized_payload_before_json_decode() -> None:
    with pytest.raises(SmokeConfigError):
        expected_labels("x" * (MAX_EXPECTED_LABELS_JSON_CHARS + 1))

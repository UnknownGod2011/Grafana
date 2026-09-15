#!/usr/bin/env python3
"""Contract tests for operator-visible timeline payload projection."""
from timeline_projection import reconciliation_timeline_payload, timeline_payload


STATIC_FIELDS = {
    "investigation_completed": ("revision", "status"),
}


def test_canonical_reconciliation_projection_is_bounded():
    event_type = "remediation_reconciliation_attempt.accepted.durable_dispatching"
    payload = {
        "result": "accepted",
        "reason": "durable_dispatching",
        "operation_id": "sg-secret-operation",
        "provider_body": {"token": "must-not-leak"},
        "target": "production-feed",
        "credential": "must-not-leak",
    }

    assert reconciliation_timeline_payload(event_type, payload) == {
        "result": "accepted",
        "reason": "durable_dispatching",
    }


def test_reconciliation_projection_rejects_event_payload_contradiction():
    assert reconciliation_timeline_payload(
        "remediation_reconciliation_recovered.accepted.legacy_unknown",
        {"result": "unknown", "reason": "legacy_unknown"},
    ) == {}


def test_reconciliation_projection_rejects_unknown_schema_values():
    assert reconciliation_timeline_payload(
        "remediation_reconciliation_attempt.pending.durable_dispatching",
        {"result": "pending", "reason": "durable_dispatching"},
    ) == {}
    assert reconciliation_timeline_payload(
        "remediation_reconciliation_retry.accepted.durable_dispatching",
        {"result": "accepted", "reason": "durable_dispatching"},
    ) == {}


def test_reconciliation_projection_rejects_noncanonical_names():
    assert reconciliation_timeline_payload(
        "remediation_reconciliation_attempt.accepted",
        {"result": "accepted", "reason": "durable_dispatching"},
    ) == {}
    assert reconciliation_timeline_payload(
        "remediation_reconciliation_attempt.accepted.durable_dispatching.extra",
        {"result": "accepted", "reason": "durable_dispatching"},
    ) == {}


def test_reconciliation_projection_rejects_oversized_event_name_before_parsing():
    event_type = (
        "remediation_reconciliation_attempt.accepted.durable_dispatching"
        + "." + ("x" * 4096)
    )
    assert reconciliation_timeline_payload(
        event_type,
        {"result": "accepted", "reason": "durable_dispatching"},
    ) == {}


def test_central_projection_preserves_static_allowlist_and_drops_extra_fields():
    assert timeline_payload(
        "investigation_completed",
        {"revision": "r1", "status": "diagnosed", "secret": "drop-me"},
        STATIC_FIELDS,
    ) == {"revision": "r1", "status": "diagnosed"}


def test_central_projection_delegates_only_canonical_reconciliation_events():
    payload = {
        "result": "accepted",
        "reason": "durable_dispatching",
        "operation_id": "must-not-leak",
        "provider_body": {"credential": "must-not-leak"},
    }
    assert timeline_payload(
        "remediation_reconciliation_attempt.accepted.durable_dispatching",
        payload,
        STATIC_FIELDS,
    ) == {"result": "accepted", "reason": "durable_dispatching"}
    assert timeline_payload("future_event", payload, STATIC_FIELDS) == {}


def test_central_projection_fails_closed_for_invalid_inputs():
    assert timeline_payload(None, {}, STATIC_FIELDS) == {}
    assert timeline_payload("investigation_completed", None, STATIC_FIELDS) == {}
    assert timeline_payload("investigation_completed", {}, None) == {}

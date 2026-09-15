#!/usr/bin/env python3
"""Contract tests for operator-visible timeline payload projection."""
from timeline_projection import reconciliation_timeline_payload


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

#!/usr/bin/env python3
"""Public audit timeline regressions for reconciliation disclosure policy."""
from types import SimpleNamespace

from incident_service import AuditEvent, IncidentService, MemoryAuditLog


def _service_with_event(event: AuditEvent) -> IncidentService:
    service = IncidentService(object(), object(), MemoryAuditLog())
    service._snapshot = SimpleNamespace(incident_id=event.incident_id)
    service._timeline.append(event)
    return service


def test_audit_timeline_exposes_only_bounded_reconciliation_fields():
    event = AuditEvent(
        sequence=7,
        timestamp_unix_ms=123456,
        incident_id="incident-1",
        event_type="remediation_reconciliation_attempt.accepted.durable_dispatching",
        actor="operator@example.invalid",
        payload={
            "result": "accepted",
            "reason": "durable_dispatching",
            "operation_id": "provider-operation-secret",
            "provider_body": {"credential": "must-not-leak"},
            "target": "live-production-feed",
            "credential": "must-not-leak",
        },
    )
    service = _service_with_event(event)

    timeline = service.audit_timeline(incident_id="incident-1")

    assert len(timeline["events"]) == 1
    projected = timeline["events"][0]
    assert projected["event_type"] == event.event_type
    assert projected["payload"] == {
        "result": "accepted",
        "reason": "durable_dispatching",
    }
    assert "operator@example.invalid" not in str(projected)
    assert "provider-operation-secret" not in str(projected)
    assert "must-not-leak" not in str(projected)
    assert "live-production-feed" not in str(projected)


def test_audit_timeline_fails_closed_for_invalid_reconciliation_payload():
    event = AuditEvent(
        sequence=8,
        timestamp_unix_ms=123457,
        incident_id="incident-2",
        event_type="remediation_reconciliation_recovered.accepted.legacy_unknown",
        actor="stageguard",
        payload={
            "result": "unknown",
            "reason": "legacy_unknown",
            "operation_id": "must-not-leak",
        },
    )
    service = _service_with_event(event)

    timeline = service.audit_timeline(incident_id="incident-2")

    assert timeline["events"][0]["payload"] == {}
    assert "must-not-leak" not in str(timeline)

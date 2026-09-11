import json
import unittest

from api import _lifecycle_view
from evidence_errors import EvidenceUnavailable
from gemini_commander import GeminiCommander
from incident_service import IncidentService, MemoryAuditLog
from remediation import ActionResult


class FailingMetrics:
    """Return one symptom sample, then fail the required causal evidence read."""

    def __init__(self) -> None:
        self.calls = 0

    def instant(self, _query):
        self.calls += 1
        if self.calls == 1:
            return 4.0
        raise EvidenceUnavailable("provider-token=super-secret upstream=private.example")


class NoopRemediation:
    def __init__(self) -> None:
        self.calls = []

    def recover_uplink(self, production_id, uplink):
        self.calls.append((production_id, uplink))
        return ActionResult(True, "accepted")


class ShouldNotRunModel:
    def __init__(self) -> None:
        self.calls = 0

    def generate(self, _context):
        self.calls += 1
        raise AssertionError("Gemini model must not run while evidence is unavailable")


class EvidenceUnavailableLifecycleTests(unittest.TestCase):
    def make_service(self, *, commander=None):
        metrics = FailingMetrics()
        remediation = NoopRemediation()
        audit = MemoryAuditLog()
        service = IncidentService(
            metrics,
            remediation,
            audit,
            commander=commander,
            clock_ms=lambda: 123456789,
            id_factory=lambda: "incident-evidence-unavailable",
            recovery_sleep=lambda _: None,
        )
        return service, metrics, remediation, audit

    def test_service_and_api_expose_sanitized_first_class_unavailability(self):
        service, metrics, remediation, audit = self.make_service()

        snapshot = service.investigate(actor="operator@example.com")

        self.assertEqual("abstain", snapshot.report.status)
        self.assertEqual(("causal",), snapshot.report.unavailable_evidence)
        self.assertEqual((), snapshot.report.missing_evidence)
        self.assertEqual(2, metrics.calls)
        self.assertIsNone(snapshot.approval)
        self.assertEqual([], remediation.calls)

        lifecycle = _lifecycle_view(service, snapshot)
        report = lifecycle["incident"]["report"]
        self.assertEqual("abstain", report["status"])
        self.assertEqual(["causal"], report["unavailable_evidence"])
        self.assertEqual([], report["missing_evidence"])

        serialized = json.dumps(lifecycle, sort_keys=True)
        self.assertNotIn("super-secret", serialized)
        self.assertNotIn("private.example", serialized)
        self.assertNotIn("provider-token", serialized)

        self.assertEqual(1, len(audit.events))
        self.assertEqual("investigation_completed", audit.events[0].event_type)
        self.assertEqual("abstain", audit.events[0].payload["status"])
        self.assertNotIn("super-secret", json.dumps(audit.events[0].payload, sort_keys=True))

    def test_gemini_briefing_is_rejected_before_model_invocation(self):
        model = ShouldNotRunModel()
        service, _metrics, _remediation, audit = self.make_service(commander=GeminiCommander(model))
        snapshot = service.investigate(actor="operator@example.com")
        before = list(audit.events)

        with self.assertRaisesRegex(ValueError, "disabled while required incident evidence is unavailable"):
            service.briefing(
                incident_id=snapshot.incident_id,
                revision=snapshot.revision,
                actor="operator@example.com",
            )

        self.assertEqual(0, model.calls)
        self.assertEqual(before, audit.events)
        self.assertEqual(["investigation_completed"], [event.event_type for event in audit.events])

    def test_approval_rejection_creates_no_approval_record_or_provider_call(self):
        service, _metrics, remediation, audit = self.make_service()
        snapshot = service.investigate(actor="operator@example.com")
        before = list(audit.events)

        with self.assertRaisesRegex(ValueError, "only a diagnosed incident"):
            service.approve(
                incident_id=snapshot.incident_id,
                revision=snapshot.revision,
                approved_by="operator@example.com",
            )

        current = service.status()
        self.assertIsNotNone(current)
        self.assertIsNone(current.approval)
        self.assertEqual(before, audit.events)
        self.assertEqual(["investigation_completed"], [event.event_type for event in audit.events])
        self.assertEqual([], remediation.calls)

    def test_audit_timeline_is_sanitized_and_does_not_invent_missing_telemetry(self):
        service, _metrics, _remediation, _audit = self.make_service()
        snapshot = service.investigate(actor="operator@example.com")

        timeline = service.audit_timeline(incident_id=snapshot.incident_id)
        self.assertEqual(1, len(timeline["events"]))
        event = timeline["events"][0]
        self.assertEqual("investigation_completed", event["event_type"])
        self.assertEqual("abstain", event["payload"]["status"])

        serialized = json.dumps(timeline, sort_keys=True)
        self.assertNotIn("super-secret", serialized)
        self.assertNotIn("private.example", serialized)
        self.assertNotIn("provider-token", serialized)
        self.assertNotIn("missing_evidence", serialized)


if __name__ == "__main__":
    unittest.main()

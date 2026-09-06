import tempfile
import unittest
from pathlib import Path

from incident_service import IncidentService, JsonlAuditLog, MemoryAuditLog
from remediation import ActionResult


class SequenceMetrics:
    def __init__(self, values):
        self.values = list(values)
        self.index = 0

    def instant(self, _query):
        if self.index >= len(self.values):
            raise AssertionError("unexpected metric query")
        value = self.values[self.index]
        self.index += 1
        return value


class FakeRemediation:
    def __init__(self, accepted=True):
        self.accepted = accepted
        self.calls = []

    def recover_uplink(self, production_id, uplink):
        self.calls.append((production_id, uplink))
        return ActionResult(self.accepted, "ok" if self.accepted else "rejected")


def diagnosed_then_recovered_metrics():
    # Six investigation reads, then two healthy recovery attempts (2 metrics each).
    return SequenceMetrics([
        4.0,   # symptom
        18.0,  # causal
        41.0,  # CPU contradiction
        37.0,  # GPU contradiction
        0.2,   # healthy uplink-a
        0.1,   # healthy peer drops
        0.2, 0.2,  # recovery streak 1
        0.1, 0.1,  # recovery streak 2
    ])


class IncidentServiceTests(unittest.TestCase):
    def make_service(self, metrics=None):
        audit = MemoryAuditLog()
        action = FakeRemediation()
        service = IncidentService(
            metrics or diagnosed_then_recovered_metrics(),
            action,
            audit,
            clock_ms=lambda: 123456789,
            id_factory=lambda: "incident-001",
            recovery_sleep=lambda _: None,
        )
        return service, action, audit

    def test_full_diagnose_approve_act_verify_lifecycle(self):
        service, action, audit = self.make_service()
        first = service.investigate()
        self.assertEqual("diagnosed", first.report.status)
        self.assertIsNone(first.approval)

        approved = service.approve(
            incident_id=first.incident_id,
            revision=first.revision,
            approved_by="operator@example.com",
        )
        self.assertTrue(approved.approval.approved)

        final = service.execute_approved()
        self.assertEqual("recovered", final.outcome.status)
        self.assertEqual([("broadcast-alpha", "uplink-b")], action.calls)
        self.assertEqual(
            ["investigation_completed", "remediation_approved", "remediation_completed"],
            [event.event_type for event in audit.events],
        )
        self.assertEqual([1, 2, 3], [event.sequence for event in audit.events])

    def test_stale_revision_cannot_be_approved(self):
        service, action, _ = self.make_service()
        snapshot = service.investigate()
        with self.assertRaises(ValueError):
            service.approve(
                incident_id=snapshot.incident_id,
                revision="stale-revision",
                approved_by="operator@example.com",
            )
        self.assertEqual([], action.calls)

    def test_cannot_approve_abstained_incident(self):
        metrics = SequenceMetrics([4.0, None, 41.0, 37.0, 0.2, 0.1])
        service, action, _ = self.make_service(metrics)
        snapshot = service.investigate()
        self.assertEqual("abstain", snapshot.report.status)
        with self.assertRaises(ValueError):
            service.approve(
                incident_id=snapshot.incident_id,
                revision=snapshot.revision,
                approved_by="operator@example.com",
            )
        self.assertEqual([], action.calls)

    def test_execution_requires_approval(self):
        service, action, _ = self.make_service()
        service.investigate()
        with self.assertRaises(RuntimeError):
            service.execute_approved()
        self.assertEqual([], action.calls)

    def test_approval_is_single_use(self):
        service, action, _ = self.make_service()
        snapshot = service.investigate()
        service.approve(
            incident_id=snapshot.incident_id,
            revision=snapshot.revision,
            approved_by="operator@example.com",
        )
        service.execute_approved()
        with self.assertRaises(RuntimeError):
            service.execute_approved()
        self.assertEqual(1, len(action.calls))

    def test_fresh_investigation_invalidates_previous_approval(self):
        metrics = SequenceMetrics([
            4.0, 18.0, 41.0, 37.0, 0.2, 0.1,
            4.0, 18.0, 41.0, 37.0, 0.2, 0.1,
        ])
        service, action, _ = self.make_service(metrics)
        snapshot = service.investigate()
        service.approve(
            incident_id=snapshot.incident_id,
            revision=snapshot.revision,
            approved_by="operator@example.com",
        )
        refreshed = service.investigate()
        self.assertIsNone(refreshed.approval)
        with self.assertRaises(RuntimeError):
            service.execute_approved()
        self.assertEqual([], action.calls)

    def test_jsonl_audit_appends_without_truncating(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "audit.jsonl"
            service, _, _ = self.make_service()
            audit = JsonlAuditLog(path)
            persisted = IncidentService(
                diagnosed_then_recovered_metrics(),
                FakeRemediation(),
                audit,
                clock_ms=lambda: 1,
                id_factory=lambda: "incident-001",
                recovery_sleep=lambda _: None,
            )
            persisted.investigate()
            first_size = path.stat().st_size
            self.assertGreater(first_size, 0)

            # Re-opening the sink must preserve existing records.
            JsonlAuditLog(path)
            self.assertEqual(first_size, path.stat().st_size)


if __name__ == "__main__":
    unittest.main()

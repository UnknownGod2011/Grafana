from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from anchored_incident_service import AnchoredIncidentService, AnchoredJsonlAuditLog
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


class NoopRemediation:
    def recover_uplink(self, _production_id, _uplink):
        return ActionResult(True, "ok", {})


class FailOnSaveStore:
    """Retain the last durable checkpoint while one selected save fails non-CAS."""

    def __init__(self, fail_on_save: int):
        self.fail_on_save = fail_on_save
        self.save_calls = 0
        self.current = None

    def load(self):
        return self.current

    def save(self, checkpoint):
        self.save_calls += 1
        if self.save_calls == self.fail_on_save:
            raise RuntimeError("simulated durable checkpoint outage")
        self.current = checkpoint


def diagnosed_values():
    return [4.0, 18.0, 41.0, 37.0, 0.2, 0.1]


class AnchoredTransitionFailureAuthorityTests(unittest.TestCase):
    def make_service(self, root: Path, values, store):
        audit = AnchoredJsonlAuditLog(root / "audit.jsonl")
        service = AnchoredIncidentService(
            SequenceMetrics(values),
            NoopRemediation(),
            audit,
            checkpoint_store=store,
            audit_anchor_interval=1,
            clock_ms=lambda: 123456789,
            id_factory=lambda: "incident-transition-failure",
            recovery_sleep=lambda _: None,
        )
        return service, audit

    def test_failed_reinvestigation_keeps_previous_snapshot_authoritative(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = FailOnSaveStore(fail_on_save=2)
            second = [5.0, 19.0, 42.0, 36.0, 0.3, 0.2]
            service, audit = self.make_service(root, diagnosed_values() + second, store)

            committed = service.investigate(actor="operator@example.com")
            self.assertEqual("verified", service.audit_integrity_state())

            with self.assertRaisesRegex(RuntimeError, "checkpoint outage"):
                service.investigate(actor="operator@example.com")

            self.assertEqual(committed, service.status())
            self.assertEqual(committed.revision, store.current.revision)
            self.assertEqual("failed", service.audit_integrity_state())
            self.assertEqual(2, len(audit.read_candidates(
                incident_id=committed.incident_id,
                after_sequence=0,
                through_sequence=2,
            )))

            with self.assertRaisesRegex(RuntimeError, "timeline is unavailable"):
                service.audit_timeline(incident_id=committed.incident_id)
            with self.assertRaisesRegex(RuntimeError, "audit integrity verification failed"):
                service.investigate(actor="operator@example.com")

    def test_failed_approval_never_publishes_uncommitted_permission(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = FailOnSaveStore(fail_on_save=2)
            service, audit = self.make_service(root, diagnosed_values(), store)

            committed = service.investigate(actor="operator@example.com")
            self.assertIsNone(committed.approval)

            with self.assertRaisesRegex(RuntimeError, "checkpoint outage"):
                service.approve(
                    incident_id=committed.incident_id,
                    revision=committed.revision,
                    approved_by="operator@example.com",
                )

            current = service.status()
            self.assertEqual(committed, current)
            self.assertIsNotNone(current)
            self.assertIsNone(current.approval)
            self.assertIsNone(store.current.approval)
            self.assertEqual("failed", service.audit_integrity_state())

            candidates = audit.read_candidates(
                incident_id=committed.incident_id,
                after_sequence=0,
                through_sequence=2,
            )
            self.assertEqual(
                ["investigation_completed", "remediation_approved"],
                [event.event_type for event in candidates],
            )
            with self.assertRaisesRegex(RuntimeError, "timeline is unavailable"):
                service.audit_timeline(incident_id=committed.incident_id)
            with self.assertRaisesRegex(RuntimeError, "audit integrity verification failed"):
                service.approve(
                    incident_id=committed.incident_id,
                    revision=committed.revision,
                    approved_by="operator@example.com",
                )


if __name__ == "__main__":
    unittest.main()

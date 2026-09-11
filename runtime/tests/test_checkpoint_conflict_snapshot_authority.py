import unittest

from incident_checkpoint import CheckpointConflictError
from incident_service import IncidentService, MemoryAuditLog
from remediation import ActionResult


class SequenceMetrics:
    def __init__(self, values):
        self.values = list(values)
        self.index = 0

    def instant(self, _query):
        value = self.values[self.index]
        self.index += 1
        return value


class NoopRemediation:
    def recover_uplink(self, _production_id, _uplink):
        return ActionResult(True, "ok")


class ConflictOnSaveStore:
    """Keep the previous durable winner when a selected save loses CAS."""

    def __init__(self, conflict_on_save):
        self.conflict_on_save = conflict_on_save
        self.save_calls = 0
        self.current = None

    def load(self):
        return self.current

    def save(self, checkpoint):
        self.save_calls += 1
        if self.save_calls == self.conflict_on_save:
            raise CheckpointConflictError("simulated concurrent winner")
        self.current = checkpoint


def diagnosed_values():
    return [4.0, 18.0, 41.0, 37.0, 0.2, 0.1]


class CheckpointConflictSnapshotAuthorityTests(unittest.TestCase):
    def make_service(self, metrics, store):
        audit = MemoryAuditLog()
        service = IncidentService(
            metrics,
            NoopRemediation(),
            audit,
            checkpoint_store=store,
            clock_ms=lambda: 123456789,
            id_factory=lambda: "incident-checkpoint-conflict",
            recovery_sleep=lambda _: None,
        )
        return service, audit

    def test_losing_reinvestigation_does_not_replace_committed_snapshot(self):
        first = diagnosed_values()
        second = [5.0, 19.0, 42.0, 36.0, 0.3, 0.2]
        store = ConflictOnSaveStore(conflict_on_save=2)
        service, audit = self.make_service(SequenceMetrics(first + second), store)

        committed = service.investigate(actor="operator@example.com")
        self.assertEqual("synchronized", service.checkpoint_state())
        self.assertEqual(committed, service.status())

        with self.assertRaises(CheckpointConflictError):
            service.investigate(actor="operator@example.com")

        self.assertEqual("conflicted", service.checkpoint_state())
        self.assertEqual(committed, service.status())
        self.assertEqual(committed.revision, store.current.revision)
        self.assertEqual(2, len(audit.events))
        self.assertEqual("investigation_completed", audit.events[-1].event_type)

        timeline = service.audit_timeline(incident_id=committed.incident_id)
        self.assertEqual(1, len(timeline["events"]))
        self.assertEqual(committed.revision, timeline["events"][0]["payload"]["revision"])

        with self.assertRaisesRegex(RuntimeError, "explicit reload"):
            service.investigate(actor="operator@example.com")

        restored = service.reload_checkpoint_after_conflict()
        self.assertEqual(committed, restored)
        self.assertEqual(committed, service.status())
        self.assertEqual("synchronized", service.checkpoint_state())

    def test_losing_approval_does_not_publish_uncommitted_approval(self):
        store = ConflictOnSaveStore(conflict_on_save=2)
        service, audit = self.make_service(SequenceMetrics(diagnosed_values()), store)
        committed = service.investigate(actor="operator@example.com")

        with self.assertRaises(CheckpointConflictError):
            service.approve(
                incident_id=committed.incident_id,
                revision=committed.revision,
                approved_by="operator@example.com",
            )

        current = service.status()
        self.assertEqual("conflicted", service.checkpoint_state())
        self.assertEqual(committed, current)
        self.assertIsNotNone(current)
        self.assertIsNone(current.approval)
        self.assertIsNone(store.current.approval)

        # Append-before-CAS audit residue is expected, but it must not enter the
        # authoritative in-process timeline until a winning checkpoint selects it.
        self.assertEqual(2, len(audit.events))
        self.assertEqual("remediation_approved", audit.events[-1].event_type)
        timeline = service.audit_timeline(incident_id=committed.incident_id)
        self.assertEqual(1, len(timeline["events"]))
        self.assertEqual("investigation_completed", timeline["events"][0]["event_type"])

        restored = service.reload_checkpoint_after_conflict()
        self.assertEqual(committed, restored)
        self.assertIsNone(restored.approval)
        self.assertEqual("synchronized", service.checkpoint_state())


if __name__ == "__main__":
    unittest.main()

import unittest

from execution_safety import ExecutionSafeIncidentService
from incident_service import IncidentService, MemoryAuditLog
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


class LocalRemediation:
    def __init__(self):
        self.calls = []

    def recover_uplink(self, production_id, uplink):
        self.calls.append((production_id, uplink))
        return ActionResult(True, "ok", {})


class FailSelectedSaveStore:
    """Retain the last durable checkpoint while one selected save fails non-CAS."""

    def __init__(self, fail_on_save):
        self.fail_on_save = fail_on_save
        self.save_calls = 0
        self.current = None

    def load(self):
        return self.current

    def save(self, checkpoint):
        self.save_calls += 1
        if self.save_calls == self.fail_on_save:
            raise RuntimeError("simulated checkpoint storage failure")
        self.current = checkpoint


def diagnosed():
    return [4.0, 18.0, 41.0, 37.0, 0.2, 0.1]


def diagnosed_again():
    return [5.0, 19.0, 42.0, 36.0, 0.3, 0.2]


def recovery():
    return [0.2, 0.2, 0.1, 0.1]


class TransitionFailureSnapshotAuthorityTests(unittest.TestCase):
    def make_base(self, values, store):
        audit = MemoryAuditLog()
        service = IncidentService(
            SequenceMetrics(values),
            LocalRemediation(),
            audit,
            checkpoint_store=store,
            clock_ms=lambda: 123456789,
            id_factory=lambda: "incident-transition-failure",
            recovery_sleep=lambda _: None,
        )
        return service, audit

    def test_failed_reinvestigation_restores_last_committed_snapshot_and_blocks_mutation(self):
        store = FailSelectedSaveStore(fail_on_save=2)
        service, audit = self.make_base(diagnosed() + diagnosed_again(), store)
        committed = service.investigate(actor="operator@example.com")
        durable = store.current

        with self.assertRaisesRegex(RuntimeError, "simulated checkpoint storage failure"):
            service.investigate(actor="operator@example.com")

        self.assertEqual(committed, service.status())
        self.assertIs(store.current, durable)
        self.assertEqual("failed", service.audit_integrity_state())
        self.assertEqual(2, len(audit.events), "append-before-persistence residue is retained for forensics")
        with self.assertRaisesRegex(RuntimeError, "timeline is unavailable"):
            service.audit_timeline(incident_id=committed.incident_id)
        with self.assertRaisesRegex(RuntimeError, "audit integrity"):
            service.investigate(actor="operator@example.com")

    def test_failed_approval_never_publishes_uncommitted_approval(self):
        store = FailSelectedSaveStore(fail_on_save=2)
        service, audit = self.make_base(diagnosed(), store)
        committed = service.investigate(actor="operator@example.com")

        with self.assertRaisesRegex(RuntimeError, "simulated checkpoint storage failure"):
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
        self.assertEqual("remediation_approved", audit.events[-1].event_type)
        with self.assertRaisesRegex(RuntimeError, "timeline is unavailable"):
            service.audit_timeline(incident_id=committed.incident_id)

    def test_post_provider_persistence_failure_hides_outcome_and_never_replays_action(self):
        store = FailSelectedSaveStore(fail_on_save=3)
        remediation = LocalRemediation()
        audit = MemoryAuditLog()
        service = ExecutionSafeIncidentService(
            SequenceMetrics(diagnosed() + recovery()),
            remediation,
            audit,
            checkpoint_store=store,
            clock_ms=lambda: 123456789,
            id_factory=lambda: "incident-post-provider-failure",
            recovery_sleep=lambda _: None,
        )
        investigated = service.investigate(actor="operator@example.com")
        approved = service.approve(
            incident_id=investigated.incident_id,
            revision=investigated.revision,
            approved_by="operator@example.com",
        )

        with self.assertRaisesRegex(RuntimeError, "simulated checkpoint storage failure"):
            service.execute_approved(actor="operator@example.com")

        current = service.status()
        self.assertIsNotNone(current)
        self.assertEqual(approved.approval, current.approval)
        self.assertIsNone(current.outcome, "failed persistence must not publish a remediation outcome")
        self.assertIsNone(store.current.outcome)
        self.assertEqual(1, len(remediation.calls), "provider action must be dispatched at most once")
        self.assertEqual("failed", service.audit_integrity_state())
        self.assertEqual("reloaded", service.execution_reconciliation_state())
        with self.assertRaisesRegex(RuntimeError, "uncertain"):
            service.execute_approved(actor="operator@example.com")
        self.assertEqual(1, len(remediation.calls), "uncertain execution must never replay the provider action")
        with self.assertRaisesRegex(RuntimeError, "timeline is unavailable"):
            service.audit_timeline(incident_id=approved.incident_id)


if __name__ == "__main__":
    unittest.main()

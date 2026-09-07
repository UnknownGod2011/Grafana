import unittest

from incident_checkpoint import CheckpointConflictError, IncidentCheckpoint
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


class FakeRemediation:
    def __init__(self):
        self.calls = []

    def recover_uplink(self, production_id, uplink):
        self.calls.append((production_id, uplink))
        return ActionResult(True, "ok", {})


class ConflictStore:
    """Simulates a stale writer that later reloads the winner."""

    def __init__(self):
        self.current = None
        self.fail_next_save = False
        self.loads = 0

    def load(self):
        self.loads += 1
        return self.current

    def save(self, checkpoint: IncidentCheckpoint):
        if self.fail_next_save:
            self.fail_next_save = False
            raise CheckpointConflictError("provider detail must not surface")
        self.current = checkpoint


def diagnosed():
    return [4.0, 18.0, 41.0, 37.0, 0.2, 0.1]


def recovery():
    return [0.2, 0.2, 0.1, 0.1]


class CheckpointConflictRecoveryTests(unittest.TestCase):
    def service(self, values, remediation, store):
        return IncidentService(
            SequenceMetrics(values),
            remediation,
            MemoryAuditLog(),
            checkpoint_store=store,
            clock_ms=lambda: 123456789,
            id_factory=lambda: "incident-001",
            recovery_sleep=lambda _: None,
        )

    def test_conflict_blocks_lifecycle_until_explicit_reload(self):
        store = ConflictStore()
        remediation = FakeRemediation()
        service = self.service(diagnosed() + recovery(), remediation, store)
        snapshot = service.investigate()
        winner = store.current
        self.assertEqual("synchronized", service.checkpoint_state())

        store.fail_next_save = True
        with self.assertRaises(CheckpointConflictError):
            service.approve(
                incident_id=snapshot.incident_id,
                revision=snapshot.revision,
                approved_by="operator@example.com",
            )
        self.assertEqual("conflicted", service.checkpoint_state())

        # The losing process may contain a speculative local approval, but it must
        # not be allowed to execute, investigate, or generate another persisted briefing.
        with self.assertRaisesRegex(RuntimeError, "explicit reload"):
            service.execute_approved()
        with self.assertRaisesRegex(RuntimeError, "explicit reload"):
            service.investigate()
        self.assertEqual([], remediation.calls)

        # Simulate the durable winner still containing the last synchronized state.
        store.current = winner
        restored = service.reload_checkpoint_after_conflict()
        self.assertEqual("synchronized", service.checkpoint_state())
        self.assertIsNone(restored.approval)
        self.assertIsNone(restored.outcome)
        with self.assertRaises(RuntimeError):
            service.execute_approved()

    def test_reload_adopts_winning_approval_and_preserves_single_use_semantics(self):
        store = ConflictStore()
        service = self.service(diagnosed(), FakeRemediation(), store)
        snapshot = service.investigate()

        # Build a separately persisted winner with a valid approval.
        winner_service = self.service([], FakeRemediation(), ConflictStore())
        winner_service._snapshot = snapshot
        winner_service._sequence = 1
        approval = winner_service.approve(
            incident_id=snapshot.incident_id,
            revision=snapshot.revision,
            approved_by="winner@example.com",
        ).approval
        winner = IncidentCheckpoint(snapshot.incident_id, snapshot.revision, snapshot.report, approval, None, 2)

        store.fail_next_save = True
        with self.assertRaises(CheckpointConflictError):
            service.approve(
                incident_id=snapshot.incident_id,
                revision=snapshot.revision,
                approved_by="loser@example.com",
            )
        store.current = winner
        restored = service.reload_checkpoint_after_conflict()
        self.assertEqual("winner@example.com", restored.approval.approved_by)

    def test_reload_failure_keeps_service_blocked(self):
        store = ConflictStore()
        service = self.service(diagnosed(), FakeRemediation(), store)
        snapshot = service.investigate()
        store.fail_next_save = True
        with self.assertRaises(CheckpointConflictError):
            service.approve(
                incident_id=snapshot.incident_id,
                revision=snapshot.revision,
                approved_by="operator@example.com",
            )
        store.current = None
        with self.assertRaisesRegex(RuntimeError, "could not load durable state"):
            service.reload_checkpoint_after_conflict()
        self.assertEqual("conflicted", service.checkpoint_state())

    def test_reload_is_not_general_refresh_api(self):
        store = ConflictStore()
        service = self.service(diagnosed(), FakeRemediation(), store)
        service.investigate()
        with self.assertRaisesRegex(RuntimeError, "only permitted after a conflict"):
            service.reload_checkpoint_after_conflict()


if __name__ == "__main__":
    unittest.main()

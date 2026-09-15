import unittest

from execution_safety import ExecutionSafeIncidentService
from incident_checkpoint import CheckpointConflictError, IncidentCheckpoint
from incident_service import MemoryAuditLog
from remediation import ActionResult


class SequenceMetrics:
    def __init__(self, values):
        self.values = list(values)
        self.index = 0

    def instant(self, _query):
        value = self.values[self.index]
        self.index += 1
        return value


class ConflictStore:
    def __init__(self):
        self.current = None
        self.fail_next_save = False

    def load(self):
        return self.current

    def save(self, checkpoint: IncidentCheckpoint):
        if self.fail_next_save:
            self.fail_next_save = False
            raise CheckpointConflictError("simulated CAS loss")
        self.current = checkpoint


class LocalRemediation:
    def __init__(self):
        self.calls = []

    def recover_uplink(self, production_id, uplink):
        self.calls.append((production_id, uplink))
        return ActionResult(True, "ok", {})


def diagnosed():
    return [4.0, 18.0, 41.0, 37.0, 0.2, 0.1]


def recovery():
    return [0.2, 0.2, 0.1, 0.1]


class LocalExecutionUncertaintyBarrierTests(unittest.TestCase):
    def test_reload_does_not_release_local_side_effect_uncertainty(self):
        store = ConflictStore()
        remediation = LocalRemediation()
        service = ExecutionSafeIncidentService(
            SequenceMetrics(diagnosed() + recovery() + diagnosed()),
            remediation,
            MemoryAuditLog(),
            checkpoint_store=store,
            clock_ms=lambda: 123456789,
            id_factory=lambda: "incident-local-001",
            recovery_sleep=lambda _: None,
        )
        investigated = service.investigate()
        service.approve(
            incident_id=investigated.incident_id,
            revision=investigated.revision,
            approved_by="operator@example.com",
        )
        durable_winner = store.current

        store.fail_next_save = True
        with self.assertRaises(CheckpointConflictError):
            service.execute_approved()
        self.assertEqual(1, len(remediation.calls))
        self.assertEqual("reload_required", service.execution_reconciliation_state())

        store.current = durable_winner
        service.reload_checkpoint_after_conflict()

        self.assertEqual("execution_uncertain", service.checkpoint_state())
        self.assertEqual("reloaded", service.execution_reconciliation_state())
        with self.assertRaisesRegex(RuntimeError, "uncertain"):
            service.execute_approved()
        self.assertEqual(1, len(remediation.calls), "reload must never permit replay of a local side effect")

        refreshed = service.reconcile_execution_uncertainty(actor="operator@example.com")
        self.assertIsNone(refreshed.approval)
        self.assertIsNone(refreshed.outcome)
        self.assertEqual("clear", service.execution_reconciliation_state())
        self.assertEqual(1, len(remediation.calls), "fresh Grafana evidence resolves uncertainty without replay")


if __name__ == "__main__":
    unittest.main()

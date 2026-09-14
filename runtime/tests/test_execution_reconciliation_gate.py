import unittest

from execution_safety import ExecutionSafeIncidentService
from incident_checkpoint import CheckpointConflictError
from incident_service import MemoryAuditLog
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


class ConflictStore:
    def __init__(self):
        self.current = None
        self.fail_next_save = False

    def load(self):
        return self.current

    def save(self, checkpoint):
        if self.fail_next_save:
            self.fail_next_save = False
            raise CheckpointConflictError("forced post-dispatch checkpoint conflict")
        self.current = checkpoint


class ReconcilingRemediation:
    requires_operation_reconciliation = True

    def __init__(self):
        self.dispatch_calls = []
        self.reconcile_calls = []

    def recover_uplink_idempotent(self, production_id, uplink, operation_id):
        self.dispatch_calls.append((production_id, uplink, operation_id))
        return ActionResult(True, "accepted", {"operation_id": operation_id})

    def recover_uplink(self, production_id, uplink):
        raise AssertionError("idempotent dispatch is required")

    def reconcile_operation(self, operation_id):
        self.reconcile_calls.append(operation_id)
        return "accepted"


def diagnosed():
    return [4.0, 18.0, 41.0, 37.0, 0.2, 0.1]


def recovered():
    return [0.2, 0.2, 0.1, 0.1]


class ExecutionReconciliationGateTests(unittest.TestCase):
    def test_reconcile_is_the_only_uncertain_state_escape_after_reload(self):
        store = ConflictStore()
        remediation = ReconcilingRemediation()
        service = ExecutionSafeIncidentService(
            SequenceMetrics(diagnosed() + recovered() + diagnosed()),
            remediation,
            MemoryAuditLog(),
            checkpoint_store=store,
            clock_ms=lambda: 123456789,
            id_factory=lambda: "incident-reconciliation-gate",
            recovery_sleep=lambda _: None,
        )

        investigated = service.investigate()
        service.approve(
            incident_id=investigated.incident_id,
            revision=investigated.revision,
            approved_by="operator@example.com",
        )
        durable_approved = store.current

        store.fail_next_save = True
        with self.assertRaises(CheckpointConflictError):
            service.execute_approved()

        self.assertEqual("execution_uncertain", service.checkpoint_state())
        self.assertEqual("reload_required", service.execution_reconciliation_state())
        self.assertEqual(1, len(remediation.dispatch_calls))

        with self.assertRaisesRegex(RuntimeError, "must be reloaded"):
            service.reconcile_execution_uncertainty(actor="operator@example.com")
        self.assertEqual([], remediation.reconcile_calls)

        store.current = durable_approved
        service.reload_checkpoint_after_conflict()
        self.assertEqual("reloaded", service.execution_reconciliation_state())

        with self.assertRaisesRegex(RuntimeError, "uncertain"):
            service.execute_approved()
        self.assertEqual(1, len(remediation.dispatch_calls), "uncertain execution must not replay provider dispatch")

        refreshed = service.reconcile_execution_uncertainty(actor="operator@example.com")
        self.assertEqual(1, len(remediation.reconcile_calls))
        self.assertEqual(1, len(remediation.dispatch_calls))
        self.assertIsNone(refreshed.approval)
        self.assertIsNone(refreshed.outcome)
        self.assertEqual("clear", service.execution_reconciliation_state())
        self.assertEqual("synchronized", service.checkpoint_state())


if __name__ == "__main__":
    unittest.main()

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

    def save(self, checkpoint: IncidentCheckpoint):
        if self.fail_next_save:
            self.fail_next_save = False
            raise CheckpointConflictError("provider detail must remain bounded")
        self.current = checkpoint


class ReconcilingRemediation:
    requires_operation_reconciliation = True

    def __init__(self, reconciliation="accepted"):
        self.calls = []
        self.reconciliation = reconciliation
        self.reconcile_calls = []

    def recover_uplink_idempotent(self, production_id, uplink, operation_id):
        self.calls.append((production_id, uplink, operation_id))
        return ActionResult(True, "accepted", {"operation_id": operation_id})

    def recover_uplink(self, production_id, uplink):
        raise AssertionError("production-style fake must use idempotent execution")

    def reconcile_operation(self, operation_id):
        self.reconcile_calls.append(operation_id)
        return self.reconciliation


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


class ExecutionSafetyTests(unittest.TestCase):
    def service(self, remediation, store, values):
        return ExecutionSafeIncidentService(
            SequenceMetrics(values),
            remediation,
            MemoryAuditLog(),
            checkpoint_store=store,
            clock_ms=lambda: 123456789,
            id_factory=lambda: "incident-001",
            recovery_sleep=lambda _: None,
        )

    def _approved(self, remediation, store, values):
        service = self.service(remediation, store, values)
        snapshot = service.investigate()
        approved = service.approve(
            incident_id=snapshot.incident_id,
            revision=snapshot.revision,
            approved_by="operator@example.com",
        )
        return service, approved

    def test_post_action_checkpoint_conflict_enters_execution_uncertain(self):
        store = ConflictStore()
        remediation = ReconcilingRemediation()
        service, approved = self._approved(remediation, store, diagnosed() + recovery())
        durable_winner = store.current

        store.fail_next_save = True
        with self.assertRaises(CheckpointConflictError):
            service.execute_approved()

        self.assertEqual(1, len(remediation.calls))
        self.assertEqual("execution_uncertain", service.checkpoint_state())
        self.assertEqual("reload_required", service.execution_reconciliation_state())
        with self.assertRaisesRegex(RuntimeError, "uncertain"):
            service.execute_approved()
        self.assertEqual(1, len(remediation.calls), "uncertain execution must never replay the remote action")

        store.current = durable_winner
        reloaded = service.reload_checkpoint_after_conflict()
        self.assertEqual(approved.approval, reloaded.approval)
        self.assertIsNone(reloaded.outcome)
        self.assertEqual("execution_uncertain", service.checkpoint_state())
        self.assertEqual("reloaded", service.execution_reconciliation_state())
        with self.assertRaisesRegex(RuntimeError, "uncertain"):
            service.execute_approved()
        self.assertEqual(1, len(remediation.calls))

    def test_reconciliation_requires_fresh_evidence_and_clears_stale_approval(self):
        store = ConflictStore()
        remediation = ReconcilingRemediation("accepted")
        service, _ = self._approved(remediation, store, diagnosed() + recovery() + diagnosed())
        durable_winner = store.current
        store.fail_next_save = True
        with self.assertRaises(CheckpointConflictError):
            service.execute_approved()
        operation_id = remediation.calls[0][2]
        store.current = durable_winner
        service.reload_checkpoint_after_conflict()

        refreshed = service.reconcile_execution_uncertainty(actor="operator@example.com")
        self.assertEqual([operation_id], remediation.reconcile_calls)
        self.assertIsNone(refreshed.approval)
        self.assertIsNone(refreshed.outcome)
        self.assertEqual("synchronized", service.checkpoint_state())
        self.assertEqual("clear", service.execution_reconciliation_state())
        with self.assertRaisesRegex(RuntimeError, "approval"):
            service.execute_approved()
        self.assertEqual(1, len(remediation.calls))

    def test_unknown_provider_state_keeps_execution_blocked(self):
        store = ConflictStore()
        remediation = ReconcilingRemediation("unknown")
        service, _ = self._approved(remediation, store, diagnosed() + recovery())
        durable_winner = store.current
        store.fail_next_save = True
        with self.assertRaises(CheckpointConflictError):
            service.execute_approved()
        store.current = durable_winner
        service.reload_checkpoint_after_conflict()

        with self.assertRaisesRegex(RuntimeError, "idempotency state is unresolved"):
            service.reconcile_execution_uncertainty()
        self.assertEqual("execution_uncertain", service.checkpoint_state())
        self.assertEqual(1, len(remediation.calls))

    def test_restored_pending_production_approval_is_fail_closed_without_execution(self):
        store = ConflictStore()
        original_remediation = ReconcilingRemediation()
        self._approved(original_remediation, store, diagnosed())
        self.assertIsNotNone(store.current.approval)
        self.assertIsNone(store.current.outcome)

        restarted_remediation = ReconcilingRemediation("not_found")
        restarted = self.service(restarted_remediation, store, diagnosed())

        self.assertEqual("execution_uncertain", restarted.checkpoint_state())
        self.assertEqual("reloaded", restarted.execution_reconciliation_state())
        with self.assertRaisesRegex(RuntimeError, "uncertain"):
            restarted.execute_approved()
        self.assertEqual([], restarted_remediation.calls)

        refreshed = restarted.reconcile_execution_uncertainty(actor="operator@example.com")
        self.assertEqual(1, len(restarted_remediation.reconcile_calls))
        self.assertEqual([], restarted_remediation.calls)
        self.assertIsNone(refreshed.approval)
        self.assertIsNone(refreshed.outcome)
        self.assertEqual("clear", restarted.execution_reconciliation_state())

    def test_restored_local_pending_approval_keeps_existing_local_semantics(self):
        store = ConflictStore()
        original = LocalRemediation()
        self._approved(original, store, diagnosed())

        restarted = self.service(LocalRemediation(), store, recovery())
        self.assertEqual("synchronized", restarted.checkpoint_state())
        self.assertEqual("clear", restarted.execution_reconciliation_state())

    def test_local_adapter_can_resolve_via_fresh_grafana_evidence_without_provider_lookup(self):
        store = ConflictStore()
        remediation = LocalRemediation()
        service, _ = self._approved(remediation, store, diagnosed() + recovery() + diagnosed())
        durable_winner = store.current
        store.fail_next_save = True
        with self.assertRaises(CheckpointConflictError):
            service.execute_approved()
        store.current = durable_winner
        service.reload_checkpoint_after_conflict()
        refreshed = service.reconcile_execution_uncertainty()
        self.assertIsNone(refreshed.approval)
        self.assertEqual("synchronized", service.checkpoint_state())
        self.assertEqual(1, len(remediation.calls))

    def test_reconcile_requires_durable_winner_reload_first(self):
        store = ConflictStore()
        remediation = ReconcilingRemediation()
        service, _ = self._approved(remediation, store, diagnosed() + recovery())
        store.fail_next_save = True
        with self.assertRaises(CheckpointConflictError):
            service.execute_approved()
        with self.assertRaisesRegex(RuntimeError, "must be reloaded"):
            service.reconcile_execution_uncertainty()
        self.assertEqual([], remediation.reconcile_calls)


if __name__ == "__main__":
    unittest.main()

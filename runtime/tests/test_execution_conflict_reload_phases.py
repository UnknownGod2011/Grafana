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


class PhaseConflictStore:
    supports_execution_phase = True

    def __init__(self):
        self.current = None
        self.fail_phase = None

    def load(self):
        return self.current

    def save(self, checkpoint: IncidentCheckpoint):
        phase = checkpoint.execution_phase
        if phase is None:
            phase = "resolved" if checkpoint.outcome is not None else "approved" if checkpoint.approval is not None else "none"
        if self.fail_phase == phase:
            self.fail_phase = None
            raise CheckpointConflictError("synthetic conflict")
        self.current = checkpoint


class ReconcilingRemediation:
    requires_operation_reconciliation = True

    def __init__(self):
        self.calls = []
        self.reconcile_calls = []

    def recover_uplink_idempotent(self, production_id, uplink, operation_id):
        self.calls.append((production_id, uplink, operation_id))
        return ActionResult(True, "accepted", {"operation_id": operation_id})

    def recover_uplink(self, production_id, uplink):
        raise AssertionError("idempotent production path required")

    def reconcile_operation(self, operation_id):
        self.reconcile_calls.append(operation_id)
        return "accepted"


def diagnosed():
    return [4.0, 18.0, 41.0, 37.0, 0.2, 0.1]


def recovery():
    return [0.2, 0.2, 0.1, 0.1]


class ConflictReloadPhaseMatrixTests(unittest.TestCase):
    def service(self, remediation, store, values):
        return ExecutionSafeIncidentService(
            SequenceMetrics(values), remediation, MemoryAuditLog(),
            checkpoint_store=store,
            clock_ms=lambda: 123456789,
            id_factory=lambda: "incident-001",
            recovery_sleep=lambda _: None,
        )

    def ambiguous_after_provider_contact(self):
        store = PhaseConflictStore()
        remediation = ReconcilingRemediation()
        service = self.service(remediation, store, diagnosed() + recovery())
        investigated = service.investigate()
        approved = service.approve(
            incident_id=investigated.incident_id,
            revision=investigated.revision,
            approved_by="operator@example.com",
        )
        store.fail_phase = "resolved"
        with self.assertRaises(CheckpointConflictError):
            service.execute_approved()
        self.assertEqual(1, len(remediation.calls))
        self.assertEqual("execution_uncertain", service.checkpoint_state())
        self.assertEqual("dispatching", service.execution_checkpoint_phase())
        self.assertIsNotNone(service.status().outcome)
        return service, remediation, store, approved, service.status().outcome

    @staticmethod
    def winner(approved, outcome, phase):
        approval = approved.approval if phase in {"approved", "dispatching", "legacy_unknown", "resolved"} else None
        resolved_outcome = outcome if phase == "resolved" else None
        return IncidentCheckpoint(
            approved.incident_id,
            approved.revision,
            approved.report,
            approval,
            resolved_outcome,
            99,
            phase,
        )

    def test_none_winner_clears_stale_process_ambiguity_and_cannot_execute(self):
        service, remediation, store, approved, outcome = self.ambiguous_after_provider_contact()
        store.current = self.winner(approved, outcome, "none")

        reloaded = service.reload_checkpoint_after_conflict()

        self.assertIsNone(reloaded.approval)
        self.assertIsNone(reloaded.outcome)
        self.assertEqual("synchronized", service.checkpoint_state())
        self.assertEqual("clear", service.execution_reconciliation_state())
        self.assertEqual("none", service.execution_checkpoint_phase())
        with self.assertRaisesRegex(RuntimeError, "approval"):
            service.execute_approved()
        self.assertEqual(1, len(remediation.calls))

    def test_resolved_winner_clears_stale_process_ambiguity_but_consumed_approval_stays_blocked(self):
        service, remediation, store, approved, outcome = self.ambiguous_after_provider_contact()
        store.current = self.winner(approved, outcome, "resolved")

        reloaded = service.reload_checkpoint_after_conflict()

        self.assertIsNotNone(reloaded.outcome)
        self.assertEqual("synchronized", service.checkpoint_state())
        self.assertEqual("clear", service.execution_reconciliation_state())
        self.assertEqual("resolved", service.execution_checkpoint_phase())
        with self.assertRaisesRegex(RuntimeError, "already been consumed"):
            service.execute_approved()
        self.assertEqual(1, len(remediation.calls))

    def test_dispatching_winner_remains_reconciliation_gated(self):
        service, remediation, store, approved, outcome = self.ambiguous_after_provider_contact()
        operation_id = remediation.calls[0][2]
        store.current = self.winner(approved, outcome, "dispatching")

        reloaded = service.reload_checkpoint_after_conflict()

        self.assertEqual(approved.approval, reloaded.approval)
        self.assertEqual("execution_uncertain", service.checkpoint_state())
        self.assertEqual("reloaded", service.execution_reconciliation_state())
        self.assertEqual("dispatching", service.execution_checkpoint_phase())
        with self.assertRaisesRegex(RuntimeError, "uncertain"):
            service.execute_approved()
        self.assertEqual(1, len(remediation.calls))
        self.assertEqual([], remediation.reconcile_calls)
        self.assertEqual(operation_id, service._execution_uncertain_operation_id)

    def test_legacy_unknown_winner_remains_reconciliation_gated(self):
        service, remediation, store, approved, outcome = self.ambiguous_after_provider_contact()
        operation_id = remediation.calls[0][2]
        store.current = self.winner(approved, outcome, "legacy_unknown")

        service.reload_checkpoint_after_conflict()

        self.assertEqual("execution_uncertain", service.checkpoint_state())
        self.assertEqual("reloaded", service.execution_reconciliation_state())
        self.assertEqual("legacy_unknown", service.execution_checkpoint_phase())
        with self.assertRaisesRegex(RuntimeError, "uncertain"):
            service.execute_approved()
        self.assertEqual(1, len(remediation.calls))
        self.assertEqual(operation_id, service._execution_uncertain_operation_id)

    def test_approved_winner_does_not_make_a_post_dispatch_stale_approval_executable(self):
        service, remediation, store, approved, outcome = self.ambiguous_after_provider_contact()
        operation_id = remediation.calls[0][2]
        store.current = self.winner(approved, outcome, "approved")

        reloaded = service.reload_checkpoint_after_conflict()

        self.assertEqual(approved.approval, reloaded.approval)
        self.assertEqual("execution_uncertain", service.checkpoint_state())
        self.assertEqual("reloaded", service.execution_reconciliation_state())
        self.assertEqual("unknown", service.execution_checkpoint_phase())
        with self.assertRaisesRegex(RuntimeError, "uncertain"):
            service.execute_approved()
        self.assertEqual(1, len(remediation.calls), "reload must never replay a possibly consumed approval")
        self.assertEqual(operation_id, service._execution_uncertain_operation_id)


if __name__ == "__main__":
    unittest.main()

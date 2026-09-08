import threading
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from execution_safety import ExecutionSafeIncidentService
from incident_checkpoint import CheckpointConflictError
from incident_service import IncidentService, MemoryAuditLog


class CapturingPhaseStore:
    supports_execution_phase = True

    def __init__(self, *, conflict=False):
        self.saved = []
        self.conflict = conflict

    def save(self, checkpoint):
        if self.conflict:
            raise CheckpointConflictError("bounded conflict")
        self.saved.append(checkpoint)


class ExecutionReconciliationAuditTests(unittest.TestCase):
    def _service(self, *, store=None):
        service = object.__new__(ExecutionSafeIncidentService)
        service._lock = threading.RLock()
        service._snapshot = SimpleNamespace(
            incident_id="incident-sensitive",
            revision="revision-sensitive",
            report=object(),
            approval=object(),
            outcome=None,
        )
        service._checkpoint_store = store
        service._sequence = 7
        service._clock_ms = lambda: 123456789
        service._audit = MemoryAuditLog()
        service._timeline = []
        service._checkpoint_conflicted = False
        service._execution_uncertain = True
        service._execution_uncertain_operation_id = "operation-sensitive"
        service._execution_reloaded = True
        service._allow_uncertainty_investigation = False
        service._uncertain_execution_phase = "dispatching"
        service._execution_reconciliation_reason = "durable_dispatching"
        return service

    def test_attempt_audit_is_bounded_and_preserves_dispatching_barrier(self):
        store = CapturingPhaseStore()
        service = self._service(store=store)

        service._record_reconciliation_attempt(
            actor="operator@example.com",
            result="unknown",
            reason="durable_dispatching",
        )

        self.assertEqual(1, len(service._audit.events))
        event = service._audit.events[0]
        self.assertEqual(
            "remediation_reconciliation_attempt.unknown.durable_dispatching",
            event.event_type,
        )
        self.assertEqual({"result": "unknown", "reason": "durable_dispatching"}, event.payload)
        self.assertNotIn("operation-sensitive", repr(event))
        self.assertNotIn("https://", repr(event))
        self.assertEqual(1, len(store.saved))
        checkpoint = store.saved[0]
        self.assertEqual("dispatching", checkpoint.execution_phase)
        self.assertEqual(8, checkpoint.sequence)

    def test_attempt_audit_conflict_fails_closed(self):
        service = self._service(store=CapturingPhaseStore(conflict=True))

        with self.assertRaises(CheckpointConflictError):
            service._record_reconciliation_attempt(
                actor="stageguard",
                result="accepted",
                reason="durable_dispatching",
            )

        self.assertTrue(service._checkpoint_conflicted)
        self.assertFalse(service._execution_reloaded)
        self.assertTrue(service._execution_uncertain)

    def test_unknown_provider_result_records_attempt_but_not_recovery(self):
        service = self._service(store=None)

        with patch.object(ExecutionSafeIncidentService, "_provider_reconciliation", return_value="unknown"):
            with self.assertRaisesRegex(RuntimeError, "idempotency state is unresolved"):
                service.reconcile_execution_uncertainty(actor="operator@example.com")

        self.assertEqual(1, len(service._audit.events))
        self.assertEqual(
            "remediation_reconciliation_attempt.unknown.durable_dispatching",
            service._audit.events[0].event_type,
        )
        self.assertTrue(service._execution_uncertain)
        self.assertEqual("durable_dispatching", service.execution_reconciliation_reason())

    def test_authoritative_result_records_attempt_and_recovery_then_clears(self):
        service = self._service(store=None)
        fresh = SimpleNamespace(
            incident_id="incident-sensitive",
            revision="fresh-revision",
            report=object(),
            approval=None,
            outcome=None,
        )

        with patch.object(ExecutionSafeIncidentService, "_provider_reconciliation", return_value="accepted"), patch.object(
            IncidentService, "investigate", return_value=fresh
        ):
            recovered = service.reconcile_execution_uncertainty(actor="operator@example.com")

        self.assertIs(fresh, recovered)
        self.assertEqual(
            [
                "remediation_reconciliation_attempt.accepted.durable_dispatching",
                "remediation_reconciliation_recovered.accepted.durable_dispatching",
            ],
            [event.event_type for event in service._audit.events],
        )
        for event in service._audit.events:
            self.assertEqual({"result": "accepted", "reason": "durable_dispatching"}, event.payload)
            self.assertNotIn("operation-sensitive", repr(event))
        self.assertFalse(service._execution_uncertain)
        self.assertEqual("clear", service.execution_reconciliation_reason())

    def test_event_type_fails_closed_to_bounded_dimensions(self):
        event_type = ExecutionSafeIncidentService._reconciliation_audit_event_type(
            "provider-secret-stage", "provider-secret-result", "provider-secret-reason"
        )
        self.assertEqual(
            "remediation_reconciliation_attempt.unknown.phase_unavailable",
            event_type,
        )
        self.assertNotIn("secret", event_type)


if __name__ == "__main__":
    unittest.main()

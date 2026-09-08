import unittest

from api import _service_readiness
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
        if isinstance(value, BaseException):
            raise value
        return value


class PhaseFaultStore:
    supports_execution_phase = True

    def __init__(self):
        self.current = None
        self.saved_phases = []
        self.fail_phase_once = None

    @staticmethod
    def _normalized(checkpoint):
        phase = checkpoint.execution_phase
        if phase is None:
            phase = "resolved" if checkpoint.outcome is not None else ("approved" if checkpoint.approval is not None else "none")
        return IncidentCheckpoint(
            checkpoint.incident_id,
            checkpoint.revision,
            checkpoint.report,
            checkpoint.approval,
            checkpoint.outcome,
            checkpoint.sequence,
            phase,
        )

    def load(self):
        return self.current

    def save(self, checkpoint):
        checkpoint = self._normalized(checkpoint)
        phase = checkpoint.execution_phase
        self.saved_phases.append(phase)
        if phase == self.fail_phase_once:
            self.fail_phase_once = None
            raise CheckpointConflictError("injected checkpoint conflict")
        self.current = checkpoint


class FaultingRemediation:
    requires_operation_reconciliation = True

    def __init__(self, store, *, fail_execute=False, reconciliation="not_found"):
        self.store = store
        self.fail_execute = fail_execute
        self.reconciliation = reconciliation
        self.execute_calls = []
        self.reconcile_calls = []

    def recover_uplink_idempotent(self, production_id, uplink, operation_id):
        self.execute_calls.append(operation_id)
        if self.store.current is None or self.store.current.execution_phase != "dispatching":
            raise AssertionError("provider contacted before durable dispatching barrier")
        if self.fail_execute:
            raise RuntimeError("injected provider failure")
        return ActionResult(True, "accepted", {})

    def recover_uplink(self, production_id, uplink):
        raise AssertionError("idempotent production path required")

    def reconcile_operation(self, operation_id):
        self.reconcile_calls.append(operation_id)
        return self.reconciliation


class ReadyResult:
    def to_dict(self):
        return {"ready": True, "checks": {}}


class ReadyProbe:
    def check(self):
        return ReadyResult()


def diagnosed():
    return [4.0, 18.0, 41.0, 37.0, 0.2, 0.1]


def recovered():
    return [0.2, 0.2, 0.1, 0.1]


def readiness(service):
    service._readiness_probe = ReadyProbe()
    return _service_readiness(service)


class ExecutionCrashMatrixTests(unittest.TestCase):
    def service(self, store, remediation, values):
        return ExecutionSafeIncidentService(
            SequenceMetrics(values),
            remediation,
            MemoryAuditLog(),
            checkpoint_store=store,
            clock_ms=lambda: 123456789,
            id_factory=lambda: "incident-001",
            recovery_sleep=lambda _: None,
        )

    def investigated(self, store, remediation, values=None):
        service = self.service(store, remediation, diagnosed() if values is None else values)
        return service, service.investigate()

    def approved(self, store, remediation, values=None):
        service, snapshot = self.investigated(store, remediation, values)
        service.approve(
            incident_id=snapshot.incident_id,
            revision=snapshot.revision,
            approved_by="operator@example.com",
        )
        return service

    def assert_blocked_readiness(self, service, expected_phase):
        state = readiness(service)
        self.assertFalse(state["ready"])
        self.assertEqual(expected_phase, state["checks"]["remediation_execution_phase"])

    def test_approved_save_failure_never_contacts_provider_and_restart_requires_approval(self):
        store = PhaseFaultStore()
        remediation = FaultingRemediation(store)
        service, snapshot = self.investigated(store, remediation)
        store.fail_phase_once = "approved"

        with self.assertRaises(CheckpointConflictError):
            service.approve(
                incident_id=snapshot.incident_id,
                revision=snapshot.revision,
                approved_by="operator@example.com",
            )

        self.assertEqual([], remediation.execute_calls)
        self.assertEqual("none", store.current.execution_phase)
        self.assertEqual("conflicted", service.checkpoint_state())
        self.assert_blocked_readiness(service, "approved")

        restarted = self.service(store, FaultingRemediation(store), [])
        self.assertEqual("synchronized", restarted.checkpoint_state())
        self.assertEqual("none", restarted.execution_checkpoint_phase())
        self.assertIsNone(restarted.status().approval)
        self.assertTrue(readiness(restarted)["ready"])

    def test_dispatching_save_failure_never_contacts_provider_and_preserves_unused_approval(self):
        store = PhaseFaultStore()
        remediation = FaultingRemediation(store)
        service = self.approved(store, remediation)
        store.fail_phase_once = "dispatching"

        with self.assertRaises(CheckpointConflictError):
            service.execute_approved()

        self.assertEqual([], remediation.execute_calls)
        self.assertEqual("approved", store.current.execution_phase)
        self.assertEqual("conflicted", service.checkpoint_state())
        self.assert_blocked_readiness(service, "approved")

        restarted_remediation = FaultingRemediation(store)
        restarted = self.service(store, restarted_remediation, recovered())
        self.assertEqual("synchronized", restarted.checkpoint_state())
        self.assertEqual("approved", restarted.execution_checkpoint_phase())
        self.assertIsNotNone(restarted.status().approval)
        self.assertEqual("clear", restarted.execution_reconciliation_state())
        self.assertTrue(readiness(restarted)["ready"])

    def test_provider_failure_after_barrier_requires_reconciliation_and_never_replays(self):
        store = PhaseFaultStore()
        remediation = FaultingRemediation(store, fail_execute=True)
        service = self.approved(store, remediation)

        with self.assertRaisesRegex(RuntimeError, "provider failure"):
            service.execute_approved()

        self.assertEqual(1, len(remediation.execute_calls))
        self.assertEqual("dispatching", store.current.execution_phase)
        self.assertEqual("execution_uncertain", service.checkpoint_state())
        self.assert_blocked_readiness(service, "dispatching")

        restarted_remediation = FaultingRemediation(store, reconciliation="not_found")
        restarted = self.service(store, restarted_remediation, diagnosed())
        self.assertEqual("execution_uncertain", restarted.checkpoint_state())
        self.assertEqual([], restarted_remediation.execute_calls)
        self.assert_blocked_readiness(restarted, "dispatching")
        refreshed = restarted.reconcile_execution_uncertainty(actor="operator@example.com")
        self.assertEqual(1, len(restarted_remediation.reconcile_calls))
        self.assertEqual([], restarted_remediation.execute_calls)
        self.assertIsNone(refreshed.approval)
        self.assertEqual("none", restarted.execution_checkpoint_phase())

    def test_grafana_verification_failure_after_provider_acceptance_never_replays(self):
        store = PhaseFaultStore()
        remediation = FaultingRemediation(store)
        service = self.approved(store, remediation, diagnosed() + [RuntimeError("injected Grafana read failure")])

        with self.assertRaisesRegex(RuntimeError, "Grafana read failure"):
            service.execute_approved()

        self.assertEqual(1, len(remediation.execute_calls))
        self.assertEqual("dispatching", store.current.execution_phase)
        self.assertEqual("execution_uncertain", service.checkpoint_state())
        self.assert_blocked_readiness(service, "dispatching")

        restarted_remediation = FaultingRemediation(store, reconciliation="accepted")
        restarted = self.service(store, restarted_remediation, diagnosed())
        refreshed = restarted.reconcile_execution_uncertainty(actor="operator@example.com")
        self.assertEqual(1, len(restarted_remediation.reconcile_calls))
        self.assertEqual([], restarted_remediation.execute_calls)
        self.assertIsNone(refreshed.approval)
        self.assertEqual("none", restarted.execution_checkpoint_phase())

    def test_resolved_save_conflict_after_verified_recovery_never_replays(self):
        store = PhaseFaultStore()
        remediation = FaultingRemediation(store)
        service = self.approved(store, remediation, diagnosed() + recovered())
        store.fail_phase_once = "resolved"

        with self.assertRaises(CheckpointConflictError):
            service.execute_approved()

        self.assertEqual(1, len(remediation.execute_calls))
        self.assertEqual("dispatching", store.current.execution_phase)
        self.assertEqual("execution_uncertain", service.checkpoint_state())
        self.assertEqual("reload_required", service.execution_reconciliation_state())
        self.assert_blocked_readiness(service, "dispatching")

        restarted_remediation = FaultingRemediation(store, reconciliation="accepted")
        restarted = self.service(store, restarted_remediation, diagnosed())
        self.assertEqual("reloaded", restarted.execution_reconciliation_state())
        refreshed = restarted.reconcile_execution_uncertainty(actor="operator@example.com")
        self.assertEqual(1, len(restarted_remediation.reconcile_calls))
        self.assertEqual([], restarted_remediation.execute_calls)
        self.assertIsNone(refreshed.approval)
        self.assertEqual("none", restarted.execution_checkpoint_phase())
        self.assertTrue(readiness(restarted)["ready"])


if __name__ == "__main__":
    unittest.main()

import hashlib
import json
import unittest

from execution_safety import ExecutionSafeIncidentService
from incident_checkpoint import IncidentCheckpoint, parse_checkpoint_document
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


class PhaseStore:
    supports_execution_phase = True

    def __init__(self):
        self.current = None
        self.saved_phases = []

    def load(self):
        return self.current

    def save(self, checkpoint: IncidentCheckpoint):
        phase = checkpoint.execution_phase
        if phase is None:
            phase = "resolved" if checkpoint.outcome is not None else ("approved" if checkpoint.approval is not None else "none")
            checkpoint = IncidentCheckpoint(
                checkpoint.incident_id, checkpoint.revision, checkpoint.report,
                checkpoint.approval, checkpoint.outcome, checkpoint.sequence, phase,
            )
        self.saved_phases.append(phase)
        self.current = checkpoint


class ReconcilingRemediation:
    requires_operation_reconciliation = True

    def __init__(self, store, reconciliation="not_found"):
        self.store = store
        self.calls = []
        self.reconcile_calls = []
        self.reconciliation = reconciliation

    def recover_uplink_idempotent(self, production_id, uplink, operation_id):
        self.calls.append((production_id, uplink, operation_id))
        if self.store.current.execution_phase != "dispatching":
            raise AssertionError("provider contacted before durable dispatching barrier")
        return ActionResult(True, "accepted", {})

    def recover_uplink(self, production_id, uplink):
        raise AssertionError("idempotent production path required")

    def reconcile_operation(self, operation_id):
        self.reconcile_calls.append(operation_id)
        return self.reconciliation


def diagnosed():
    return [4.0, 18.0, 41.0, 37.0, 0.2, 0.1]


def recovery():
    return [0.2, 0.2, 0.1, 0.1]


class ExecutionPhaseV2Tests(unittest.TestCase):
    def service(self, remediation, store, values):
        return ExecutionSafeIncidentService(
            SequenceMetrics(values), remediation, MemoryAuditLog(),
            checkpoint_store=store,
            clock_ms=lambda: 123456789,
            id_factory=lambda: "incident-001",
            recovery_sleep=lambda _: None,
        )

    def approved(self, store, remediation):
        service = self.service(remediation, store, diagnosed() + recovery())
        snapshot = service.investigate()
        service.approve(
            incident_id=snapshot.incident_id,
            revision=snapshot.revision,
            approved_by="operator@example.com",
        )
        return service

    def test_dispatching_is_durable_before_provider_contact(self):
        store = PhaseStore()
        remediation = ReconcilingRemediation(store)
        service = self.approved(store, remediation)
        self.assertEqual("approved", store.current.execution_phase)

        final = service.execute_approved()

        self.assertEqual(1, len(remediation.calls))
        self.assertIn("dispatching", store.saved_phases)
        self.assertEqual("resolved", store.current.execution_phase)
        self.assertEqual("recovered", final.outcome.status)
        self.assertLess(store.saved_phases.index("dispatching"), store.saved_phases.index("resolved"))

    def test_v2_approved_restart_is_not_execution_ambiguous(self):
        store = PhaseStore()
        original = ReconcilingRemediation(store)
        self.approved(store, original)
        self.assertEqual("approved", store.current.execution_phase)

        restarted_remediation = ReconcilingRemediation(store)
        restarted = self.service(restarted_remediation, store, recovery())

        self.assertEqual("synchronized", restarted.checkpoint_state())
        self.assertEqual("clear", restarted.execution_reconciliation_state())
        restarted.execute_approved()
        self.assertEqual(1, len(restarted_remediation.calls))
        self.assertEqual([], restarted_remediation.reconcile_calls)

    def test_dispatching_restart_requires_reconciliation_without_replay(self):
        store = PhaseStore()
        remediation = ReconcilingRemediation(store)
        self.approved(store, remediation)
        pending = store.current
        store.current = IncidentCheckpoint(
            pending.incident_id, pending.revision, pending.report,
            pending.approval, pending.outcome, pending.sequence, "dispatching",
        )

        restarted_remediation = ReconcilingRemediation(store, "not_found")
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
        self.assertEqual("clear", restarted.execution_reconciliation_state())

    def test_legacy_v1_pending_approval_remains_fail_closed(self):
        store = PhaseStore()
        remediation = ReconcilingRemediation(store)
        self.approved(store, remediation)
        checkpoint = store.current
        state = {
            "incident_id": checkpoint.incident_id,
            "revision": checkpoint.revision,
            "report": checkpoint.report.to_dict(),
            "approval": {
                "approved": checkpoint.approval.approved,
                "approved_by": checkpoint.approval.approved_by,
                "action": checkpoint.approval.action,
                "production_id": checkpoint.approval.production_id,
                "target": checkpoint.approval.target,
            },
            "outcome": None,
            "sequence": checkpoint.sequence,
        }
        canonical = json.dumps(state, sort_keys=True, separators=(",", ":")).encode("utf-8")
        legacy = parse_checkpoint_document({
            "schema": "stageguard.incident-checkpoint.v1",
            "state": state,
            "sha256": hashlib.sha256(canonical).hexdigest(),
            "hmac_sha256": None,
        })
        store.current = legacy

        restarted = self.service(ReconcilingRemediation(store), store, diagnosed())
        self.assertEqual("execution_uncertain", restarted.checkpoint_state())
        self.assertEqual("legacy_unknown", store.current.execution_phase)


if __name__ == "__main__":
    unittest.main()

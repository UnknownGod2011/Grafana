from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from anchored_execution_safety import AnchoredExecutionSafeIncidentService
from anchored_incident_service import AnchoredJsonlAuditLog
from incident_checkpoint import CheckpointConflictError, IncidentCheckpoint
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


class OutcomeConflictStore:
    """Keep the durable dispatching winner and reject the first outcome commit."""

    supports_execution_phase = True

    def __init__(self):
        self.current: IncidentCheckpoint | None = None
        self.reject_outcome = True

    def load(self):
        return self.current

    def save(self, checkpoint: IncidentCheckpoint):
        if self.reject_outcome and checkpoint.outcome is not None:
            self.reject_outcome = False
            raise CheckpointConflictError("lost outcome CAS")
        self.current = checkpoint


class ReconcilingRemediation:
    requires_operation_reconciliation = True

    def __init__(self):
        self.calls = []

    def recover_uplink_idempotent(self, production_id, uplink, operation_id):
        self.calls.append((production_id, uplink, operation_id))
        return ActionResult(True, "accepted", {"operation_id": operation_id})

    def recover_uplink(self, _production_id, _uplink):
        raise AssertionError("production-style remediation must use the idempotent operation path")

    def reconcile_operation(self, _operation_id):
        return "accepted"


def diagnosed():
    return [4.0, 18.0, 41.0, 37.0, 0.2, 0.1]


def recovery():
    return [0.2, 0.2, 0.1, 0.1]


class ExecutionOutcomeCheckpointAuthorityTests(unittest.TestCase):
    def test_losing_outcome_commit_never_becomes_read_authority_or_replays_provider(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = OutcomeConflictStore()
            remediation = ReconcilingRemediation()
            service = AnchoredExecutionSafeIncidentService(
                SequenceMetrics(diagnosed() + recovery()),
                remediation,
                AnchoredJsonlAuditLog(root / "audit.jsonl"),
                checkpoint_store=store,
                audit_anchor_interval=32,
                clock_ms=lambda: 123456789,
                id_factory=lambda: "incident-outcome-authority-001",
                recovery_sleep=lambda _: None,
            )

            investigated = service.investigate()
            approved = service.approve(
                incident_id=investigated.incident_id,
                revision=investigated.revision,
                approved_by="operator@example.com",
            )
            self.assertIsNone(approved.outcome)

            with self.assertRaisesRegex(CheckpointConflictError, "lost outcome CAS"):
                service.execute_approved(actor="operator@example.com")

            self.assertEqual(1, len(remediation.calls), "the provider action is allowed exactly once")
            visible = service.status()
            self.assertIsNotNone(visible)
            self.assertEqual(approved.approval, visible.approval)
            self.assertIsNone(
                visible.outcome,
                "a losing remediation outcome must not be exposed as committed lifecycle state",
            )
            self.assertEqual("execution_uncertain", service.checkpoint_state())
            self.assertEqual("reload_required", service.execution_reconciliation_state())
            self.assertEqual("dispatching", service.execution_checkpoint_phase())

            self.assertIsNotNone(store.current)
            self.assertEqual("dispatching", store.current.execution_phase)
            self.assertIsNone(store.current.outcome)

            timeline = service.audit_timeline(incident_id=approved.incident_id, limit=20)
            event_types = [event["event_type"] for event in timeline["events"]]
            self.assertNotIn(
                "remediation_completed",
                event_types,
                "append-before-CAS loser residue must not enter committed operator history",
            )

            with self.assertRaisesRegex(RuntimeError, "uncertain"):
                service.execute_approved(actor="operator@example.com")
            self.assertEqual(1, len(remediation.calls), "uncertainty must block provider replay")

            reloaded = service.reload_checkpoint_after_conflict()
            self.assertEqual(approved.approval, reloaded.approval)
            self.assertIsNone(reloaded.outcome)
            self.assertEqual("execution_uncertain", service.checkpoint_state())
            self.assertEqual("reloaded", service.execution_reconciliation_state())
            self.assertEqual("dispatching", service.execution_checkpoint_phase())

            with self.assertRaisesRegex(RuntimeError, "uncertain"):
                service.execute_approved(actor="operator@example.com")
            self.assertEqual(1, len(remediation.calls), "reload alone must never replay the provider action")


if __name__ == "__main__":
    unittest.main()

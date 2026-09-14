from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from anchored_execution_safety import AnchoredExecutionSafeIncidentService
from anchored_incident_service import AnchoredJsonlAuditLog
from incident_checkpoint import JsonCheckpointStore
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


class CountingRemediation:
    def __init__(self):
        self.calls = 0

    def recover_uplink(self, _production_id, _uplink):
        self.calls += 1
        return ActionResult(True, "ok", {})


class ForbiddenRemediation:
    def recover_uplink(self, _production_id, _uplink):
        raise AssertionError("recovery-only verification must not replay remediation after restart")


class RecoveryRecheckRestartTests(unittest.TestCase):
    def test_unverified_recovery_restores_and_rechecks_without_provider_replay(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            audit_path = root / "audit.jsonl"
            store = JsonCheckpointStore(root / "checkpoint.json")
            first_remediation = CountingRemediation()
            first = AnchoredExecutionSafeIncidentService(
                SequenceMetrics([
                    4.0, 18.0, 41.0, 37.0, 0.2, 0.1,
                    *([8.0, 5.0] * 6),
                ]),
                first_remediation,
                AnchoredJsonlAuditLog(audit_path),
                checkpoint_store=store,
                audit_anchor_interval=1,
                clock_ms=lambda: 123456789,
                id_factory=lambda: "incident-recheck-restart-001",
                recovery_sleep=lambda _: None,
            )
            investigated = first.investigate()
            first.approve(
                incident_id=investigated.incident_id,
                revision=investigated.revision,
                approved_by="operator@example.com",
            )
            initial = first.execute_approved(actor="operator@example.com")
            self.assertEqual("recovery_unverified", initial.outcome.status)
            self.assertEqual(1, first_remediation.calls)

            restarted = AnchoredExecutionSafeIncidentService(
                SequenceMetrics([0.2, 0.2, 0.1, 0.1]),
                ForbiddenRemediation(),
                AnchoredJsonlAuditLog(audit_path),
                checkpoint_store=store,
                audit_anchor_interval=1,
                clock_ms=lambda: 123456790,
                id_factory=lambda: "must-not-create-new-incident",
                recovery_sleep=lambda _: None,
            )

            restored = restarted.status()
            self.assertIsNotNone(restored)
            self.assertEqual(initial.incident_id, restored.incident_id)
            self.assertEqual(initial.revision, restored.revision)
            self.assertEqual("recovery_unverified", restored.outcome.status)
            self.assertEqual("clear", restarted.execution_reconciliation_state())
            self.assertEqual("synchronized", restarted.checkpoint_state())

            final = restarted.recheck_recovery(actor="operator@example.com")
            self.assertEqual("recovered", final.outcome.status)
            self.assertEqual(initial.incident_id, final.incident_id)
            self.assertEqual(initial.revision, final.revision)
            timeline = restarted.audit_timeline(incident_id=final.incident_id, limit=20)
            self.assertEqual("recovery_rechecked", timeline["events"][-1]["event_type"])
            self.assertEqual(False, timeline["events"][-1]["payload"]["provider_replayed"])


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from anchored_execution_safety import AnchoredExecutionSafeIncidentService
from anchored_incident_service import AnchoredJsonlAuditLog
from api import _lifecycle_view, _service_metrics, _service_readiness
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


class ConstantMetrics:
    def __init__(self, value=0.1):
        self.value = value

    def instant(self, _query):
        return self.value


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
                ConstantMetrics(),
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

            lifecycle = _lifecycle_view(restarted, restored)
            self.assertEqual(
                {
                    "state": "recovery_unverified",
                    "action_accepted": True,
                    "recheck_eligible": True,
                    "verified": False,
                    "sample_count": 6,
                    "checkpoint_phase_consistent": True,
                },
                lifecycle["recovery"],
            )
            metrics = _service_metrics(restarted)
            self.assertIn('stageguard_recovery_state{state="recovery_unverified"} 1', metrics)
            self.assertIn("stageguard_recovery_recheck_eligible 1", metrics)
            self.assertIn("stageguard_recovery_verified 0", metrics)
            self.assertIn("stageguard_recovery_checkpoint_phase_consistent 1", metrics)
            self.assertNotIn(restored.incident_id, metrics)
            self.assertNotIn(restored.revision, metrics)
            readiness = _service_readiness(restarted)
            self.assertEqual("recovery_unverified", readiness["checks"]["recovery_state"])
            self.assertEqual("yes", readiness["checks"]["recovery_recheck_eligible"])
            self.assertEqual("no", readiness["checks"]["recovery_verified"])
            self.assertEqual("consistent", readiness["checks"]["recovery_checkpoint_phase"])

            final = restarted.recheck_recovery(actor="operator@example.com")
            self.assertEqual("recovered", final.outcome.status)
            self.assertEqual(initial.incident_id, final.incident_id)
            self.assertEqual(initial.revision, final.revision)
            timeline = restarted.audit_timeline(incident_id=final.incident_id, limit=20)
            self.assertEqual("recovery_rechecked", timeline["events"][-1]["event_type"])
            self.assertEqual(False, timeline["events"][-1]["payload"]["provider_replayed"])

            recovered_view = _lifecycle_view(restarted, final)
            self.assertEqual("recovered", recovered_view["recovery"]["state"])
            self.assertTrue(recovered_view["recovery"]["verified"])
            self.assertFalse(recovered_view["recovery"]["recheck_eligible"])
            self.assertTrue(recovered_view["recovery"]["checkpoint_phase_consistent"])
            with self.assertRaisesRegex(RuntimeError, "only allowed while recovery remains unverified"):
                restarted.recheck_recovery(actor="operator@example.com")
            with self.assertRaises(RuntimeError):
                restarted.execute_approved(actor="operator@example.com")


if __name__ == "__main__":
    unittest.main()

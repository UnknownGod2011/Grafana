from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from anchored_execution_safety import AnchoredExecutionSafeIncidentService
from anchored_incident_service import AnchoredIncidentService, AnchoredJsonlAuditLog
from execution_safety import ExecutionSafeIncidentService
from incident_checkpoint import JsonCheckpointStore, checkpoint_document
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


class FakeRemediation:
    def recover_uplink(self, _production_id, _uplink):
        return ActionResult(True, "ok", {})


def diagnosed(repeats: int = 1):
    return [4.0, 18.0, 41.0, 37.0, 0.2, 0.1] * repeats


class AnchoredExecutionSafetyCompositionTests(unittest.TestCase):
    def service(self, metrics, audit_path, store, *, interval=1):
        return AnchoredExecutionSafeIncidentService(
            SequenceMetrics(metrics),
            FakeRemediation(),
            AnchoredJsonlAuditLog(audit_path),
            checkpoint_store=store,
            audit_anchor_interval=interval,
            clock_ms=lambda: 123456789,
            id_factory=lambda: "incident-anchor-exec-001",
            recovery_sleep=lambda _: None,
        )

    def test_mro_preserves_both_runtime_contracts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            service = self.service(
                diagnosed(),
                root / "audit.jsonl",
                JsonCheckpointStore(root / "checkpoint.json"),
            )
            self.assertIsInstance(service, AnchoredIncidentService)
            self.assertIsInstance(service, ExecutionSafeIncidentService)
            self.assertEqual("clear", service.execution_reconciliation_state())
            self.assertEqual("synchronized", service.checkpoint_state())

    def test_execution_safe_composition_emits_v4_and_restarts_from_compacted_prefix(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            audit_path = root / "audit.jsonl"
            store = JsonCheckpointStore(root / "checkpoint.json")

            first = self.service(diagnosed(), audit_path, store)
            first.investigate()
            checkpoint = store.load()
            self.assertEqual("stageguard.incident-checkpoint.v4", checkpoint_document(checkpoint)["schema"])
            self.assertEqual("verified", first.audit_integrity_state())
            self.assertEqual("clear", first.execution_reconciliation_state())

            audit_path.write_text("", encoding="utf-8")
            restarted = self.service([], audit_path, store)
            self.assertEqual("verified", restarted.audit_integrity_state())
            self.assertEqual("synchronized", restarted.checkpoint_state())
            self.assertEqual("clear", restarted.execution_reconciliation_state())
            self.assertEqual(checkpoint.revision, restarted.status().revision)

    def test_checkpoint_conflict_keeps_anchor_untrusted_and_execution_layer_available(self):
        class ConflictStore:
            supports_execution_phase = True

            def load(self):
                return None

            def save(self, _checkpoint):
                from incident_checkpoint import CheckpointConflictError
                raise CheckpointConflictError("lost CAS")

        with tempfile.TemporaryDirectory() as directory:
            service = self.service(
                diagnosed(),
                Path(directory) / "audit.jsonl",
                ConflictStore(),
            )
            with self.assertRaisesRegex(Exception, "lost CAS"):
                service.investigate()
            self.assertFalse(service._audit_anchor_authenticated)
            self.assertEqual(0, service._audit_anchor.sequence)
            self.assertEqual("conflicted", service.checkpoint_state())
            self.assertEqual("clear", service.execution_reconciliation_state())


if __name__ == "__main__":
    unittest.main()

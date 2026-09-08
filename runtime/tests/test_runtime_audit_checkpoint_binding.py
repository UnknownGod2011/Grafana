from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from execution_safety import ExecutionSafeIncidentService
from incident_checkpoint import JsonCheckpointStore, checkpoint_document
from incident_service import IncidentService, JsonlAuditLog
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


class ReconciledRemediation(FakeRemediation):
    requires_operation_reconciliation = True

    def reconcile_operation(self, _operation_id):
        return "accepted"


def diagnosed():
    return [4.0, 18.0, 41.0, 37.0, 0.2, 0.1]


class RuntimeAuditCheckpointBindingTests(unittest.TestCase):
    def service(self, cls, metrics, remediation, audit_path, store):
        return cls(
            SequenceMetrics(metrics),
            remediation,
            JsonlAuditLog(audit_path),
            checkpoint_store=store,
            clock_ms=lambda: 123456789,
            id_factory=lambda: "incident-001",
            recovery_sleep=lambda _: None,
        )

    def test_jsonl_runtime_emits_v3_and_verifies_after_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            audit_path = root / "audit.jsonl"
            store = JsonCheckpointStore(root / "checkpoint.json")

            first = self.service(IncidentService, diagnosed(), FakeRemediation(), audit_path, store)
            first.investigate()
            checkpoint = store.load()

            self.assertEqual("stageguard.incident-checkpoint.v3", checkpoint_document(checkpoint)["schema"])
            self.assertEqual(checkpoint.sequence, checkpoint.audit_chain_sequence)
            self.assertEqual(64, len(checkpoint.audit_chain_head_sha256))
            self.assertEqual("verified", first.audit_integrity_state())

            restarted = self.service(ExecutionSafeIncidentService, [], FakeRemediation(), audit_path, store)
            self.assertEqual("verified", restarted.audit_integrity_state())
            self.assertEqual("synchronized", restarted.checkpoint_state())
            self.assertEqual(checkpoint.revision, restarted.status().revision)

    def test_mutated_durable_audit_fails_closed_after_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            audit_path = root / "audit.jsonl"
            store = JsonCheckpointStore(root / "checkpoint.json")

            first = self.service(IncidentService, diagnosed(), FakeRemediation(), audit_path, store)
            first.investigate()

            lines = audit_path.read_text(encoding="utf-8").splitlines()
            raw = json.loads(lines[0])
            raw["actor"] = "tampered-operator@example.com"
            lines[0] = json.dumps(raw, sort_keys=True, separators=(",", ":"))
            audit_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

            restarted = self.service(ExecutionSafeIncidentService, [], FakeRemediation(), audit_path, store)
            self.assertEqual("failed", restarted.audit_integrity_state())
            self.assertEqual("conflicted", restarted.checkpoint_state())
            with self.assertRaisesRegex(RuntimeError, "audit integrity verification failed"):
                restarted.investigate()

    def test_orphan_tail_beyond_authenticated_head_fails_closed_on_restore(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            audit_path = root / "audit.jsonl"
            store = JsonCheckpointStore(root / "checkpoint.json")

            first = self.service(IncidentService, diagnosed(), FakeRemediation(), audit_path, store)
            first.investigate()
            checkpoint = store.load()
            self.assertEqual(1, checkpoint.sequence)
            self.assertEqual(1, checkpoint.audit_chain_sequence)

            orphan = {
                "sequence": 2,
                "timestamp_unix_ms": 123456790,
                "incident_id": checkpoint.incident_id,
                "event_type": "remediation_approved",
                "actor": "losing-writer@example.com",
                "payload": {"revision": checkpoint.revision, "action": "recover_primary_uplink"},
            }
            with audit_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(orphan, sort_keys=True, separators=(",", ":")) + "\n")

            restarted = self.service(ExecutionSafeIncidentService, [], FakeRemediation(), audit_path, store)
            self.assertEqual("failed", restarted.audit_integrity_state())
            self.assertEqual("conflicted", restarted.checkpoint_state())
            self.assertEqual(checkpoint.sequence, restarted._sequence)
            self.assertIsNone(restarted.status().approval)
            with self.assertRaisesRegex(RuntimeError, "audit integrity verification failed"):
                restarted.investigate()

    def test_conflicting_duplicate_at_authenticated_sequence_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            audit_path = root / "audit.jsonl"
            store = JsonCheckpointStore(root / "checkpoint.json")

            first = self.service(IncidentService, diagnosed(), FakeRemediation(), audit_path, store)
            first.investigate()
            checkpoint = store.load()

            original = json.loads(audit_path.read_text(encoding="utf-8").splitlines()[0])
            duplicate = dict(original)
            duplicate["actor"] = "conflicting-writer@example.com"
            with audit_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(duplicate, sort_keys=True, separators=(",", ":")) + "\n")

            restarted = self.service(ExecutionSafeIncidentService, [], FakeRemediation(), audit_path, store)
            self.assertEqual("failed", restarted.audit_integrity_state())
            self.assertEqual("conflicted", restarted.checkpoint_state())
            self.assertEqual(checkpoint.sequence, restarted._sequence)

    def test_dispatching_barrier_preserves_authenticated_chain_head(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            audit_path = root / "audit.jsonl"
            store = JsonCheckpointStore(root / "checkpoint.json")
            service = self.service(
                ExecutionSafeIncidentService,
                diagnosed(),
                ReconciledRemediation(),
                audit_path,
                store,
            )
            snapshot = service.investigate()
            service.approve(
                incident_id=snapshot.incident_id,
                revision=snapshot.revision,
                approved_by="operator@example.com",
            )
            approved = store.load()
            self.assertEqual("approved", approved.execution_phase)
            self.assertIsNotNone(approved.audit_chain_head_sha256)

            self.assertTrue(service._persist_dispatching_barrier(service.status()))
            dispatching = store.load()
            self.assertEqual("dispatching", dispatching.execution_phase)
            self.assertEqual(approved.audit_chain_sequence, dispatching.audit_chain_sequence)
            self.assertEqual(approved.audit_chain_head_sha256, dispatching.audit_chain_head_sha256)
            self.assertEqual("stageguard.incident-checkpoint.v3", checkpoint_document(dispatching)["schema"])


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from anchored_incident_service import AnchoredIncidentService, AnchoredJsonlAuditLog
from incident_checkpoint import JsonCheckpointStore, checkpoint_document
from incident_service import AuditEvent
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
    def __init__(self):
        self.calls = 0

    def recover_uplink(self, _production_id, _uplink):
        self.calls += 1
        return ActionResult(True, "ok", {})


def diagnosed(repeats: int = 1):
    return [4.0, 18.0, 41.0, 37.0, 0.2, 0.1] * repeats


class AnchoredIncidentRuntimeTests(unittest.TestCase):
    def service(self, metrics, audit_path, store, *, interval):
        return AnchoredIncidentService(
            SequenceMetrics(metrics),
            FakeRemediation(),
            AnchoredJsonlAuditLog(audit_path),
            checkpoint_store=store,
            audit_anchor_interval=interval,
            clock_ms=lambda: 123456789,
            id_factory=lambda: "incident-anchor-001",
            recovery_sleep=lambda _: None,
        )

    def test_jsonl_candidate_reader_honors_exclusive_anchor_bound(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "audit.jsonl"
            audit = AnchoredJsonlAuditLog(path)
            for sequence in (1, 2, 3):
                audit.append(
                    AuditEvent(
                        sequence,
                        123456789 + sequence,
                        "incident-anchor-001",
                        "investigation_completed",
                        "stageguard",
                        {"revision": f"r{sequence}"},
                    )
                )

            selected = audit.read_candidates(
                incident_id="incident-anchor-001",
                after_sequence=1,
                through_sequence=3,
            )
            self.assertEqual([2, 3], [event.sequence for event in selected])
            self.assertEqual(
                [],
                audit.read_candidates(
                    incident_id="incident-anchor-001",
                    after_sequence=3,
                    through_sequence=3,
                ),
            )
            with self.assertRaisesRegex(ValueError, "cannot exceed"):
                audit.read_candidates(
                    incident_id="incident-anchor-001",
                    after_sequence=4,
                    through_sequence=3,
                )

    def test_restart_verifies_after_pre_anchor_records_are_physically_removed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            audit_path = root / "audit.jsonl"
            store = JsonCheckpointStore(root / "checkpoint.json")

            first = self.service(diagnosed(), audit_path, store, interval=1)
            first.investigate()
            checkpoint = store.load()

            self.assertEqual("stageguard.incident-checkpoint.v4", checkpoint_document(checkpoint)["schema"])
            self.assertEqual(checkpoint.sequence, checkpoint.audit_anchor_sequence)
            self.assertEqual(checkpoint.audit_chain_head_sha256, checkpoint.audit_anchor_head_sha256)
            self.assertEqual("verified", first.audit_integrity_state())

            audit_path.write_text("", encoding="utf-8")

            restarted = self.service([], audit_path, store, interval=1)
            self.assertEqual("verified", restarted.audit_integrity_state())
            self.assertEqual("synchronized", restarted.checkpoint_state())
            self.assertEqual(checkpoint.revision, restarted.status().revision)
            self.assertEqual(checkpoint.sequence, restarted._sequence)

    def test_post_anchor_committed_mutation_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            audit_path = root / "audit.jsonl"
            store = JsonCheckpointStore(root / "checkpoint.json")

            service = self.service(diagnosed(3), audit_path, store, interval=2)
            service.investigate()
            service.investigate()
            service.investigate()
            checkpoint = store.load()

            self.assertEqual(2, checkpoint.audit_anchor_sequence)
            self.assertEqual(3, checkpoint.audit_chain_sequence)

            lines = audit_path.read_text(encoding="utf-8").splitlines()
            suffix = []
            for line in lines:
                raw = json.loads(line)
                if raw["sequence"] <= checkpoint.audit_anchor_sequence:
                    continue
                raw["actor"] = "tampered-operator@example.com"
                suffix.append(json.dumps(raw, sort_keys=True, separators=(",", ":")))
            audit_path.write_text("\n".join(suffix) + "\n", encoding="utf-8")

            restarted = self.service([], audit_path, store, interval=2)
            self.assertEqual("failed", restarted.audit_integrity_state())
            with self.assertRaisesRegex(RuntimeError, "audit integrity verification failed"):
                restarted.investigate()

    def test_anchor_is_not_promoted_when_checkpoint_save_conflicts(self):
        class ConflictStore:
            def load(self):
                return None

            def save(self, _checkpoint):
                from incident_checkpoint import CheckpointConflictError
                raise CheckpointConflictError("lost CAS")

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "audit.jsonl"
            service = AnchoredIncidentService(
                SequenceMetrics(diagnosed()),
                FakeRemediation(),
                AnchoredJsonlAuditLog(path),
                checkpoint_store=ConflictStore(),
                audit_anchor_interval=1,
                clock_ms=lambda: 123456789,
                id_factory=lambda: "incident-anchor-001",
                recovery_sleep=lambda _: None,
            )
            with self.assertRaisesRegex(Exception, "lost CAS"):
                service.investigate()
            self.assertFalse(service._audit_anchor_authenticated)
            self.assertEqual(0, service._audit_anchor.sequence)


if __name__ == "__main__":
    unittest.main()

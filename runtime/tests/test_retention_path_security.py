import json
import os
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from audit_file_lock import assert_open_regular_file_identity
from incident_checkpoint import JsonCheckpointStore
from incident_service import AuditEvent, IncidentService, MemoryAuditLog
from remediation import ActionResult
from retention_executor import execute_local_retention, prepare_local_retention_plan
from retention_planner import plan_jsonl_retention


class SequenceMetrics:
    def __init__(self, values):
        self.values = list(values)
        self.index = 0

    def instant(self, _query):
        value = self.values[self.index]
        self.index += 1
        return value


class FakeRemediation:
    def recover_uplink(self, _production_id, _uplink):
        return ActionResult(True, "ok", {})


def diagnosed():
    return [4.0, 18.0, 41.0, 37.0, 0.2, 0.1]


class RetentionPathSecurityTests(unittest.TestCase):
    signing_key = b"p" * 32

    def checkpoint(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        store = JsonCheckpointStore(Path(directory.name) / "checkpoint.json")
        service = IncidentService(
            SequenceMetrics(diagnosed()),
            FakeRemediation(),
            MemoryAuditLog(),
            checkpoint_store=store,
            clock_ms=lambda: 123456789,
            id_factory=lambda: "incident-retention-path-security",
            recovery_sleep=lambda _: None,
        )
        service.investigate()
        checkpoint = store.load()
        self.assertIsNotNone(checkpoint)
        return replace(
            checkpoint,
            audit_chain_sequence=checkpoint.sequence,
            audit_chain_head_sha256="a" * 64,
            audit_anchor_sequence=checkpoint.sequence,
            audit_anchor_head_sha256="a" * 64,
        )

    def event(self, sequence):
        return AuditEvent(
            sequence=sequence,
            timestamp_unix_ms=123456789 + sequence,
            incident_id="incident-retention-path-security",
            event_type="investigation_completed",
            actor="system",
            payload={"revision": "r"},
        )

    def write_event(self, path, event):
        path.write_text(json.dumps(event.__dict__, sort_keys=True) + "\n", encoding="utf-8")

    @unittest.skipIf(os.name == "nt", "symlink creation requires elevated Windows privileges on many runners")
    def test_planner_refuses_symlinked_audit_file_without_reading_target_as_evidence(self):
        checkpoint = self.checkpoint()
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        victim = root / "victim.jsonl"
        audit = root / "audit.jsonl"
        self.write_event(victim, self.event(checkpoint.audit_anchor_sequence))
        audit.symlink_to(victim)

        plan = plan_jsonl_retention(checkpoint, audit, audit_integrity_state="verified")

        self.assertFalse(plan.safe_to_compact)
        self.assertIn("inventoried safely", plan.refusal_reason)
        self.assertEqual(1, len(victim.read_text(encoding="utf-8").splitlines()))

    @unittest.skipIf(os.name == "nt", "symlink creation requires elevated Windows privileges on many runners")
    def test_execute_refuses_symlink_substitution_without_mutating_target(self):
        checkpoint = self.checkpoint()
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        audit = root / "audit.jsonl"
        victim = root / "victim.txt"
        self.write_event(audit, self.event(checkpoint.audit_anchor_sequence))
        document = prepare_local_retention_plan(
            checkpoint,
            audit,
            signing_key=self.signing_key,
            audit_integrity_state="verified",
            clock_ms=lambda: 111,
        )
        victim.write_bytes(b"DO-NOT-TOUCH")
        audit.unlink()
        audit.symlink_to(victim)

        with self.assertRaises(RuntimeError):
            execute_local_retention(document, checkpoint, signing_key=self.signing_key)

        self.assertEqual(b"DO-NOT-TOUCH", victim.read_bytes())
        self.assertEqual([], list(root.glob("*.bak")))

    def test_execute_detects_path_swap_after_source_open_before_replace(self):
        checkpoint = self.checkpoint()
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        audit = root / "audit.jsonl"
        displaced = root / "original-displaced.jsonl"
        original_line = json.dumps(self.event(checkpoint.audit_anchor_sequence).__dict__, sort_keys=True) + "\n"
        audit.write_text(original_line, encoding="utf-8")
        document = prepare_local_retention_plan(
            checkpoint,
            audit,
            signing_key=self.signing_key,
            audit_integrity_state="verified",
            clock_ms=lambda: 222,
        )

        calls = 0

        def identity_check(fd, path):
            nonlocal calls
            calls += 1
            if calls == 2:
                os.replace(audit, displaced)
                audit.write_bytes(b"SUBSTITUTED-PATH")
            return assert_open_regular_file_identity(fd, path)

        with patch("retention_executor.assert_open_regular_file_identity", side_effect=identity_check):
            with self.assertRaisesRegex(RuntimeError, "path changed"):
                execute_local_retention(document, checkpoint, signing_key=self.signing_key)

        self.assertEqual(b"SUBSTITUTED-PATH", audit.read_bytes())
        self.assertEqual(original_line.encode("utf-8"), displaced.read_bytes())
        self.assertEqual([], list(root.glob(f".{audit.name}.retention-*")))


if __name__ == "__main__":
    unittest.main()

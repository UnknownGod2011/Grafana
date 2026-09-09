import hashlib
import json
import os
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from incident_checkpoint import JsonCheckpointStore
from incident_service import AuditEvent, IncidentService, MemoryAuditLog
from remediation import ActionResult
from retention_executor import (
    execute_local_retention,
    parse_signed_plan_document,
    prepare_local_retention_plan,
)


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


class RetentionExecutorTests(unittest.TestCase):
    signing_key = b"r" * 32

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
            id_factory=lambda: "incident-retention-executor",
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

    def event(self, sequence, incident_id="incident-retention-executor"):
        return AuditEvent(
            sequence=sequence,
            timestamp_unix_ms=123456789 + sequence,
            incident_id=incident_id,
            event_type="investigation_completed",
            actor="system",
            payload={"revision": "r"},
        )

    def write_events(self, path, events):
        lines = [
            (json.dumps(event.__dict__, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
            for event in events
        ]
        path.write_bytes(b"".join(lines))
        return lines

    def test_two_phase_execution_preserves_suffix_and_other_incidents_and_creates_backup(self):
        checkpoint = self.checkpoint()
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "audit.jsonl"
        boundary = checkpoint.audit_anchor_sequence
        events = [
            self.event(boundary),
            self.event(boundary),
            self.event(boundary + 1),
            self.event(1, incident_id="other-incident"),
        ]
        lines = self.write_events(path, events)
        original = path.read_bytes()

        document = prepare_local_retention_plan(
            checkpoint,
            path,
            signing_key=self.signing_key,
            audit_integrity_state="verified",
            clock_ms=lambda: 999,
        )
        plan = parse_signed_plan_document(document, signing_key=self.signing_key)
        self.assertEqual(2, plan.eligible_records)
        self.assertEqual(len(lines[0]) + len(lines[1]), plan.eligible_bytes)
        self.assertEqual(original, path.read_bytes())

        result = execute_local_retention(
            document,
            checkpoint,
            signing_key=self.signing_key,
        )

        self.assertEqual(2, result.removed_records)
        self.assertEqual(lines[2] + lines[3], path.read_bytes())
        backup = Path(result.backup_path)
        self.assertEqual(original, backup.read_bytes())
        if os.name != "nt":
            # Windows exposes ACL-backed permissions rather than POSIX mode
            # bits through stat(); the implementation still applies its
            # owner-only intent where the platform supports these bits.
            self.assertEqual(0o600, backup.stat().st_mode & 0o777)
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), result.output_sha256)

    def test_execution_refuses_checkpoint_drift_without_modifying_audit(self):
        checkpoint = self.checkpoint()
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "audit.jsonl"
        self.write_events(path, [self.event(checkpoint.audit_anchor_sequence)])
        original = path.read_bytes()
        document = prepare_local_retention_plan(
            checkpoint,
            path,
            signing_key=self.signing_key,
            audit_integrity_state="verified",
        )
        drifted = replace(checkpoint, revision="f" * 16)

        with self.assertRaisesRegex(RuntimeError, "checkpoint changed"):
            execute_local_retention(document, drifted, signing_key=self.signing_key)

        self.assertEqual(original, path.read_bytes())
        self.assertEqual([], list(path.parent.glob("*.bak")))

    def test_execution_refuses_audit_drift_without_modifying_or_backing_up(self):
        checkpoint = self.checkpoint()
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "audit.jsonl"
        self.write_events(path, [self.event(checkpoint.audit_anchor_sequence)])
        document = prepare_local_retention_plan(
            checkpoint,
            path,
            signing_key=self.signing_key,
            audit_integrity_state="verified",
        )
        with path.open("ab") as handle:
            handle.write((json.dumps(self.event(checkpoint.audit_anchor_sequence + 1).__dict__) + "\n").encode())
        drifted = path.read_bytes()

        with self.assertRaisesRegex(RuntimeError, "audit file changed"):
            execute_local_retention(document, checkpoint, signing_key=self.signing_key)

        self.assertEqual(drifted, path.read_bytes())
        self.assertEqual([], list(path.parent.glob("*.bak")))

    def test_plan_tampering_fails_authenticity_check(self):
        checkpoint = self.checkpoint()
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "audit.jsonl"
        self.write_events(path, [self.event(checkpoint.audit_anchor_sequence)])
        document = prepare_local_retention_plan(
            checkpoint,
            path,
            signing_key=self.signing_key,
            audit_integrity_state="verified",
        )
        document["plan"]["eligible_through_sequence"] += 1

        with self.assertRaises(ValueError):
            parse_signed_plan_document(document, signing_key=self.signing_key)

    def test_replace_failure_keeps_original_and_recoverable_backup(self):
        checkpoint = self.checkpoint()
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "audit.jsonl"
        self.write_events(
            path,
            [
                self.event(checkpoint.audit_anchor_sequence),
                self.event(checkpoint.audit_anchor_sequence + 1),
            ],
        )
        original = path.read_bytes()
        document = prepare_local_retention_plan(
            checkpoint,
            path,
            signing_key=self.signing_key,
            audit_integrity_state="verified",
            clock_ms=lambda: 321,
        )
        real_replace = os.replace

        def fail_replace(src, dst):
            if Path(dst) == path:
                raise OSError("simulated replace failure")
            return real_replace(src, dst)

        with patch("retention_executor.os.replace", side_effect=fail_replace):
            with self.assertRaisesRegex(OSError, "simulated replace failure"):
                execute_local_retention(document, checkpoint, signing_key=self.signing_key)

        self.assertEqual(original, path.read_bytes())
        backups = list(path.parent.glob("*.bak"))
        self.assertEqual(1, len(backups))
        self.assertEqual(original, backups[0].read_bytes())
        self.assertEqual([], list(path.parent.glob(f".{path.name}.retention-*")))

    def test_refuses_unverified_prepare(self):
        checkpoint = self.checkpoint()
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "audit.jsonl"
        self.write_events(path, [self.event(checkpoint.audit_anchor_sequence)])

        with self.assertRaisesRegex(ValueError, "audit integrity is not verified"):
            prepare_local_retention_plan(
                checkpoint,
                path,
                signing_key=self.signing_key,
                audit_integrity_state="failed",
            )


if __name__ == "__main__":
    unittest.main()

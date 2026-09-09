from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from bootstrap import build_runtime
from incident_checkpoint import JsonCheckpointStore, checkpoint_document
from incident_service import AuditEvent, IncidentService, MemoryAuditLog
from remediation import ActionResult


class SequenceMetrics:
    datasource_uid = "prom-main"

    def __init__(self, values):
        self.values = list(values)
        self.index = 0
        self.closed = False

    def instant(self, _query):
        value = self.values[self.index]
        self.index += 1
        return value

    def close(self):
        self.closed = True


class FakeRemediation:
    def recover_uplink(self, _production_id, _uplink):
        return ActionResult(True, "ok", {})


class CountingRemediation(FakeRemediation):
    def __init__(self):
        self.calls = 0

    def recover_uplink(self, _production_id, _uplink):
        self.calls += 1
        return ActionResult(True, "ok", {})


def _diagnosed():
    return [4.0, 18.0, 41.0, 37.0, 0.2, 0.1]


def _diagnosed_with_recovery():
    return [4.0, 18.0, 41.0, 37.0, 0.2, 0.1, 0.1, 0.1, 0.1, 0.1]


class RetentionCoordinatorCliAcceptanceTests(unittest.TestCase):
    signing_key_text = "c" * 32

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.audit_path = self.root / "audit.jsonl"
        self.checkpoint_path = self.root / "checkpoint.json"
        self.plan_path = self.root / "retention-plan.json"
        self.backup_path = self.root / "audit.backup.jsonl"
        self.runtime_dir = Path(__file__).resolve().parents[1]
        self.coordinator = self.runtime_dir / "retention_coordinator.py"

        store = JsonCheckpointStore(self.root / "seed-checkpoint.json")
        service = IncidentService(
            SequenceMetrics(_diagnosed()),
            FakeRemediation(),
            MemoryAuditLog(),
            checkpoint_store=store,
            clock_ms=lambda: 123456789,
            id_factory=lambda: "incident-retention-cli",
            recovery_sleep=lambda _: None,
        )
        service.investigate()
        checkpoint = store.load()
        self.assertIsNotNone(checkpoint)
        assert checkpoint is not None
        self.checkpoint = replace(
            checkpoint,
            audit_chain_sequence=checkpoint.sequence,
            audit_chain_head_sha256="a" * 64,
            audit_anchor_sequence=checkpoint.sequence,
            audit_anchor_head_sha256="a" * 64,
        )
        signed = checkpoint_document(
            self.checkpoint,
            signing_key=self.signing_key_text.encode("utf-8"),
        )
        self.checkpoint_path.write_text(
            json.dumps(signed, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )

    def _event(self, sequence, incident_id="incident-retention-cli"):
        return AuditEvent(
            sequence=sequence,
            timestamp_unix_ms=123456789 + sequence,
            incident_id=incident_id,
            event_type="investigation_completed",
            actor="system",
            payload={"revision": "r"},
        )

    def _write_events(self, events):
        encoded = [
            (json.dumps(event.__dict__, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
            for event in events
        ]
        self.audit_path.write_bytes(b"".join(encoded))
        return encoded

    def _run(self, *args, check=True):
        env = os.environ.copy()
        env["STAGEGUARD_CHECKPOINT_HMAC_KEY"] = self.signing_key_text
        return subprocess.run(
            [sys.executable, str(self.coordinator), *map(str, args)],
            cwd=str(self.runtime_dir),
            env=env,
            text=True,
            capture_output=True,
            check=check,
            timeout=20,
        )

    def test_prepare_and_execute_cli_compacts_exact_prefix_and_creates_backup(self):
        boundary = self.checkpoint.audit_anchor_sequence
        assert boundary is not None
        lines = self._write_events(
            [
                self._event(boundary),
                self._event(boundary),
                self._event(boundary + 1),
                self._event(1, incident_id="other-incident"),
            ]
        )
        original = self.audit_path.read_bytes()

        prepared = self._run(
            "prepare",
            "--checkpoint", self.checkpoint_path,
            "--audit-jsonl", self.audit_path,
            "--plan-out", self.plan_path,
            "--audit-integrity-state", "verified",
        )
        prepared_status = json.loads(prepared.stdout)
        self.assertEqual("prepared", prepared_status["status"])
        self.assertTrue(self.plan_path.exists())
        self.assertEqual(original, self.audit_path.read_bytes())

        executed = self._run(
            "execute",
            "--checkpoint", self.checkpoint_path,
            "--plan", self.plan_path,
            "--backup", self.backup_path,
        )
        executed_status = json.loads(executed.stdout)
        self.assertEqual("executed", executed_status["status"])
        self.assertEqual(2, executed_status["removed_records"])
        self.assertEqual(lines[2] + lines[3], self.audit_path.read_bytes())
        self.assertEqual(original, self.backup_path.read_bytes())
        self.assertEqual(0o600, self.backup_path.stat().st_mode & 0o777)

    def test_execute_cli_refuses_source_drift_after_signed_prepare(self):
        boundary = self.checkpoint.audit_anchor_sequence
        assert boundary is not None
        self._write_events([self._event(boundary), self._event(boundary + 1)])

        self._run(
            "prepare",
            "--checkpoint", self.checkpoint_path,
            "--audit-jsonl", self.audit_path,
            "--plan-out", self.plan_path,
            "--audit-integrity-state", "verified",
        )

        with self.audit_path.open("ab") as handle:
            handle.write(
                (
                    json.dumps(
                        self._event(boundary + 2).__dict__,
                        sort_keys=True,
                        separators=(",", ":"),
                    )
                    + "\n"
                ).encode("utf-8")
            )
        drifted = self.audit_path.read_bytes()

        result = self._run(
            "execute",
            "--checkpoint", self.checkpoint_path,
            "--plan", self.plan_path,
            "--backup", self.backup_path,
            check=False,
        )
        self.assertNotEqual(0, result.returncode)
        self.assertIn("audit file changed", result.stderr)
        self.assertEqual(drifted, self.audit_path.read_bytes())
        self.assertFalse(self.backup_path.exists())

    def test_signed_runtime_compaction_restart_preserves_consumed_approval_without_replay(self):
        example = self.runtime_dir / "telemetry.example.json"
        first_remediation = CountingRemediation()
        runtime_checkpoint = self.root / "runtime-checkpoint.json"
        runtime_audit = self.root / "runtime-audit.jsonl"
        runtime_plan = self.root / "runtime-retention-plan.json"
        runtime_backup = self.root / "runtime-audit.backup.jsonl"

        with patch.dict(
            os.environ,
            {"STAGEGUARD_CHECKPOINT_HMAC_KEY": self.signing_key_text},
            clear=False,
        ):
            first = build_runtime(
                telemetry_config=example,
                activation_path=None,
                audit_path=runtime_audit,
                host="127.0.0.1",
                port=0,
                checkpoint_backend="signed-json",
                checkpoint_path=runtime_checkpoint,
                checkpoint_signing_key_env="STAGEGUARD_CHECKPOINT_HMAC_KEY",
                audit_integrity_policy="require_verified",
                audit_anchor_interval=1,
                metrics_factory=lambda: SequenceMetrics(_diagnosed_with_recovery()),
                remediation_factory=lambda _profile: first_remediation,
            )
            try:
                investigated = first.service.investigate(actor="retention-cli-test")
                first.service.approve(
                    incident_id=investigated.incident_id,
                    revision=investigated.revision,
                    approved_by="operator@example.test",
                )
                completed = first.service.execute_approved(actor="retention-cli-test")
                self.assertIsNotNone(completed.outcome)
                self.assertEqual("recovered", completed.outcome.status)
                self.assertEqual(1, first_remediation.calls)
                self.assertEqual("verified", first.service.audit_integrity_state())
                self.assertGreater(first.service.audit_anchor_state()["sequence"], 0)
            finally:
                first.close()

            prepared = self._run(
                "prepare",
                "--checkpoint", runtime_checkpoint,
                "--audit-jsonl", runtime_audit,
                "--plan-out", runtime_plan,
                "--audit-integrity-state", "verified",
            )
            self.assertEqual("prepared", json.loads(prepared.stdout)["status"])

            executed = self._run(
                "execute",
                "--checkpoint", runtime_checkpoint,
                "--plan", runtime_plan,
                "--backup", runtime_backup,
            )
            self.assertEqual("executed", json.loads(executed.stdout)["status"])
            self.assertTrue(runtime_backup.exists())

            restarted_remediation = CountingRemediation()
            restarted = build_runtime(
                telemetry_config=example,
                activation_path=None,
                audit_path=runtime_audit,
                host="127.0.0.1",
                port=0,
                checkpoint_backend="signed-json",
                checkpoint_path=runtime_checkpoint,
                checkpoint_signing_key_env="STAGEGUARD_CHECKPOINT_HMAC_KEY",
                audit_integrity_policy="require_verified",
                audit_anchor_interval=1,
                metrics_factory=lambda: SequenceMetrics([]),
                remediation_factory=lambda _profile: restarted_remediation,
            )
            try:
                restored = restarted.service.status()
                self.assertIsNotNone(restored)
                assert restored is not None
                self.assertEqual("verified", restarted.service.audit_integrity_state())
                self.assertEqual("require_verified", restarted.service._audit_integrity_policy)
                self.assertEqual("synchronized", restarted.service.checkpoint_state())
                self.assertEqual("clear", restarted.service.execution_reconciliation_state())
                self.assertIsNotNone(restored.approval)
                self.assertIsNotNone(restored.outcome)
                self.assertEqual("recovered", restored.outcome.status)
                self.assertEqual(0, restarted_remediation.calls)
                with self.assertRaisesRegex(RuntimeError, "already been consumed"):
                    restarted.service.execute_approved(actor="retention-cli-test")
                self.assertEqual(0, restarted_remediation.calls)
            finally:
                restarted.close()


if __name__ == "__main__":
    unittest.main()

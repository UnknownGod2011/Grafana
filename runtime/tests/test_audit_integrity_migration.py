from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from api import _service_readiness
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


class CountingRemediation:
    def __init__(self) -> None:
        self.calls = 0

    def recover_uplink(self, _production_id, _uplink):
        self.calls += 1
        return ActionResult(True, "ok", {})


class AppendOnlyAuditSink:
    """Legacy-compatible sink that durably appends JSONL but cannot read it.

    This models an older deployment that already retained its audit stream but did
    not expose the reader capability needed to bind that stream into checkpoint
    schema v3. The migration test can therefore create a real schema-v2 document
    without hand-authoring or weakening checkpoint validation.
    """

    def __init__(self, path: Path) -> None:
        self._delegate = JsonlAuditLog(path)

    def append(self, event) -> None:
        self._delegate.append(event)


class ReadyResult:
    def to_dict(self):
        return {"ready": True, "checks": {"prometheus_mcp": "ok", "loki_mcp": "ok"}}


class ReadyProbe:
    def check(self):
        return ReadyResult()

    def prometheus_metrics(self):
        return ""


def diagnosed():
    return [4.0, 18.0, 41.0, 37.0, 0.2, 0.1]


class AuditIntegrityMigrationAcceptanceTests(unittest.TestCase):
    def service(self, metrics, remediation, audit, store):
        service = IncidentService(
            SequenceMetrics(metrics),
            remediation,
            audit,
            checkpoint_store=store,
            clock_ms=lambda: 123456789,
            id_factory=lambda: "incident-001",
            recovery_sleep=lambda _: None,
        )
        service._audit_integrity_policy = "require_verified"
        service._readiness_probe = ReadyProbe()
        return service

    def test_legacy_v2_migrates_to_verified_v3_without_replay(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            audit_path = root / "audit.jsonl"
            store = JsonCheckpointStore(root / "checkpoint.json")
            remediation = CountingRemediation()

            # A legitimate legacy runtime durably records its event but lacks an
            # audit reader, so its checkpoint remains schema v2.
            legacy = self.service(
                diagnosed(),
                remediation,
                AppendOnlyAuditSink(audit_path),
                store,
            )
            legacy_snapshot = legacy.investigate()
            legacy_checkpoint = store.load()
            self.assertEqual("stageguard.incident-checkpoint.v2", checkpoint_document(legacy_checkpoint)["schema"])
            self.assertEqual(1, legacy_checkpoint.sequence)
            self.assertIsNone(legacy_checkpoint.audit_chain_sequence)
            self.assertIsNone(legacy_checkpoint.audit_chain_head_sha256)
            self.assertIsNone(legacy_snapshot.approval)
            self.assertIsNone(legacy_snapshot.outcome)
            self.assertEqual(0, remediation.calls)

            # The hardened runtime can read and verify the complete legacy audit
            # prefix, but must remain unready until a real lifecycle write seals a
            # v3 binding. Policy does not rewrite the underlying migration state.
            migrating = self.service(
                diagnosed(),
                remediation,
                JsonlAuditLog(audit_path),
                store,
            )
            self.assertEqual("unbound_legacy", migrating.audit_integrity_state())
            before = _service_readiness(migrating)
            self.assertFalse(before["ready"])
            self.assertEqual("unbound_legacy", before["checks"]["audit_integrity"])
            self.assertEqual("require_verified", before["checks"]["audit_integrity_policy"])

            migrated_snapshot = migrating.investigate()
            migrated_checkpoint = store.load()
            migrated_document = checkpoint_document(migrated_checkpoint)
            self.assertEqual("stageguard.incident-checkpoint.v3", migrated_document["schema"])
            self.assertEqual(2, migrated_checkpoint.sequence)
            self.assertEqual(2, migrated_checkpoint.audit_chain_sequence)
            self.assertEqual(64, len(migrated_checkpoint.audit_chain_head_sha256))
            self.assertEqual("verified", migrating.audit_integrity_state())
            self.assertTrue(_service_readiness(migrating)["ready"])
            self.assertEqual(legacy_snapshot.incident_id, migrated_snapshot.incident_id)
            self.assertIsNone(migrated_snapshot.approval)
            self.assertIsNone(migrated_snapshot.outcome)
            self.assertEqual(0, remediation.calls)

            # A fresh process must verify the persisted v3 head against the same
            # durable audit pair rather than relying on in-memory migration state.
            restarted = self.service(
                [],
                remediation,
                JsonlAuditLog(audit_path),
                store,
            )
            restarted_snapshot = restarted.status()
            self.assertIsNotNone(restarted_snapshot)
            self.assertEqual("verified", restarted.audit_integrity_state())
            self.assertTrue(_service_readiness(restarted)["ready"])
            self.assertEqual("synchronized", restarted.checkpoint_state())
            self.assertEqual(2, restarted._sequence)
            self.assertEqual(migrated_snapshot.revision, restarted_snapshot.revision)
            self.assertIsNone(restarted_snapshot.approval)
            self.assertIsNone(restarted_snapshot.outcome)
            self.assertEqual(0, remediation.calls)

            events = JsonlAuditLog(audit_path).read(
                incident_id=restarted_snapshot.incident_id,
                after_sequence=0,
                limit=10,
            )
            self.assertEqual([1, 2], [event.sequence for event in events])
            self.assertEqual(
                ["investigation_completed", "investigation_completed"],
                [event.event_type for event in events],
            )


if __name__ == "__main__":
    unittest.main()

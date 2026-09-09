import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from incident_checkpoint import JsonCheckpointStore, checkpoint_document, parse_checkpoint_document
from incident_service import IncidentService, MemoryAuditLog
from remediation import ActionResult


class SequenceMetrics:
    def __init__(self, values):
        self.values = list(values)
        self.index = 0

    def instant(self, _query):
        value = self.values[self.index]
        self.index += 1
        return value


class FakeRemediation:
    def recover_uplink(self, production_id, uplink):
        return ActionResult(True, "ok", {})


def diagnosed():
    return [4.0, 18.0, 41.0, 37.0, 0.2, 0.1]


class AuditAnchorCheckpointSchemaTests(unittest.TestCase):
    def checkpoint(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        store = JsonCheckpointStore(Path(directory.name) / "checkpoint.json")
        service = IncidentService(
            SequenceMetrics(diagnosed()), FakeRemediation(), MemoryAuditLog(),
            checkpoint_store=store,
            clock_ms=lambda: 123456789,
            id_factory=lambda: "incident-anchor-schema",
            recovery_sleep=lambda _: None,
        )
        service.investigate()
        return store.load()

    def test_v4_round_trips_authenticated_anchor(self):
        checkpoint = self.checkpoint()
        bound = replace(
            checkpoint,
            audit_chain_sequence=checkpoint.sequence,
            audit_chain_head_sha256="a" * 64,
            audit_anchor_sequence=0,
            audit_anchor_head_sha256="0" * 64,
        )
        key = b"k" * 32
        document = checkpoint_document(bound, signing_key=key)
        self.assertEqual("stageguard.incident-checkpoint.v4", document["schema"])
        self.assertEqual(0, document["state"]["audit_anchor_sequence"])
        restored = parse_checkpoint_document(document, signing_key=key, require_signature=True)
        self.assertEqual(0, restored.audit_anchor_sequence)
        self.assertEqual("0" * 64, restored.audit_anchor_head_sha256)
        self.assertEqual(checkpoint.sequence, restored.audit_chain_sequence)

    def test_anchor_requires_chain_and_complete_pair(self):
        checkpoint = self.checkpoint()
        with self.assertRaisesRegex(ValueError, "supplied together"):
            checkpoint_document(replace(checkpoint, audit_anchor_sequence=0))
        with self.assertRaisesRegex(ValueError, "requires an audit-chain"):
            checkpoint_document(replace(
                checkpoint,
                audit_anchor_sequence=0,
                audit_anchor_head_sha256="0" * 64,
            ))

    def test_anchor_cannot_exceed_or_conflict_with_current_head(self):
        checkpoint = self.checkpoint()
        with self.assertRaisesRegex(ValueError, "cannot exceed"):
            checkpoint_document(replace(
                checkpoint,
                audit_chain_sequence=0,
                audit_chain_head_sha256="0" * 64,
                audit_anchor_sequence=1,
                audit_anchor_head_sha256="a" * 64,
            ))
        with self.assertRaisesRegex(ValueError, "conflicts"):
            checkpoint_document(replace(
                checkpoint,
                audit_chain_sequence=checkpoint.sequence,
                audit_chain_head_sha256="a" * 64,
                audit_anchor_sequence=checkpoint.sequence,
                audit_anchor_head_sha256="b" * 64,
            ))

    def test_v3_remains_v3_when_no_anchor_is_present(self):
        checkpoint = self.checkpoint()
        document = checkpoint_document(replace(
            checkpoint,
            audit_chain_sequence=checkpoint.sequence,
            audit_chain_head_sha256="a" * 64,
        ))
        self.assertEqual("stageguard.incident-checkpoint.v3", document["schema"])
        self.assertNotIn("audit_anchor_sequence", document["state"])

    def test_signed_anchor_tamper_fails_authenticity(self):
        checkpoint = self.checkpoint()
        key = b"k" * 32
        document = checkpoint_document(replace(
            checkpoint,
            audit_chain_sequence=checkpoint.sequence,
            audit_chain_head_sha256="a" * 64,
            audit_anchor_sequence=0,
            audit_anchor_head_sha256="0" * 64,
        ), signing_key=key)
        document["state"]["audit_anchor_head_sha256"] = "b" * 64
        canonical = json.dumps(document["state"], sort_keys=True, separators=(",", ":")).encode("utf-8")
        import hashlib
        document["sha256"] = hashlib.sha256(canonical).hexdigest()
        with self.assertRaisesRegex(ValueError, "authenticity"):
            parse_checkpoint_document(document, signing_key=key, require_signature=True)


if __name__ == "__main__":
    unittest.main()

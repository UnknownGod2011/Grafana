import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from incident_checkpoint import JsonCheckpointStore
from incident_service import AuditEvent, IncidentService, MemoryAuditLog
from remediation import ActionResult
from retention_planner import (
    plan_authenticated_boundary,
    plan_cloud_logging_retention,
    plan_jsonl_retention,
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


class RecordingReader:
    def __init__(self, events):
        self.events = list(events)
        self.calls = []

    def read_candidates(self, **kwargs):
        self.calls.append(dict(kwargs))
        boundary = kwargs["through_sequence"]
        return [event for event in self.events if event.sequence <= boundary]


def diagnosed():
    return [4.0, 18.0, 41.0, 37.0, 0.2, 0.1]


class RetentionPlannerTests(unittest.TestCase):
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
            id_factory=lambda: "incident-retention",
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

    def event(self, sequence, incident_id="incident-retention"):
        return AuditEvent(
            sequence=sequence,
            timestamp_unix_ms=123456789 + sequence,
            incident_id=incident_id,
            event_type="investigation_completed",
            actor="system",
            payload={"revision": "r"},
        )

    def test_boundary_refuses_unverified_conflicted_unbound_and_genesis(self):
        checkpoint = self.checkpoint()
        self.assertFalse(plan_authenticated_boundary(
            checkpoint, audit_integrity_state="failed"
        ).safe_to_compact)
        self.assertFalse(plan_authenticated_boundary(
            checkpoint, audit_integrity_state="verified", checkpoint_conflicted=True
        ).safe_to_compact)

        unbound = replace(
            checkpoint,
            audit_chain_sequence=None,
            audit_chain_head_sha256=None,
            audit_anchor_sequence=None,
            audit_anchor_head_sha256=None,
        )
        self.assertFalse(plan_authenticated_boundary(
            unbound, audit_integrity_state="verified"
        ).safe_to_compact)

        genesis = replace(
            checkpoint,
            audit_anchor_sequence=0,
            audit_anchor_head_sha256="0" * 64,
        )
        self.assertFalse(plan_authenticated_boundary(
            genesis, audit_integrity_state="verified"
        ).safe_to_compact)

    def test_jsonl_plan_is_exact_and_does_not_modify_file(self):
        checkpoint = self.checkpoint()
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "audit.jsonl"
        events = [
            self.event(1),
            self.event(1),
            self.event(2),
            self.event(1, incident_id="other-incident"),
        ]
        raw_lines = [
            (json.dumps(event.__dict__, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
            for event in events
        ]
        original = b"".join(raw_lines)
        path.write_bytes(original)

        plan = plan_jsonl_retention(
            checkpoint,
            path,
            audit_integrity_state="verified",
        )

        self.assertTrue(plan.safe_to_compact)
        self.assertEqual(checkpoint.audit_anchor_sequence, plan.eligible_through_sequence)
        self.assertEqual(2, plan.eligible_records)
        self.assertEqual(len(raw_lines[0]) + len(raw_lines[1]), plan.eligible_bytes)
        self.assertEqual(4, plan.scanned_records)
        self.assertTrue(plan.enumeration_complete)
        self.assertEqual(original, path.read_bytes())

    def test_jsonl_never_counts_records_after_anchor(self):
        checkpoint = self.checkpoint()
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "audit.jsonl"
        first = self.event(checkpoint.audit_anchor_sequence)
        later = self.event(checkpoint.audit_anchor_sequence + 1)
        path.write_text(
            json.dumps(first.__dict__) + "\n" + json.dumps(later.__dict__) + "\n",
            encoding="utf-8",
        )
        plan = plan_jsonl_retention(checkpoint, path, audit_integrity_state="verified")
        self.assertEqual(1, plan.eligible_records)

    def test_cloud_logging_inventory_queries_only_through_authenticated_anchor(self):
        checkpoint = self.checkpoint()
        reader = RecordingReader([
            self.event(checkpoint.audit_anchor_sequence),
            self.event(checkpoint.audit_anchor_sequence + 1),
        ])

        plan = plan_cloud_logging_retention(
            checkpoint,
            reader,
            audit_integrity_state="verified",
        )

        self.assertTrue(plan.safe_to_compact)
        self.assertEqual(1, plan.eligible_records)
        self.assertFalse(plan.enumeration_complete)
        self.assertIsNone(plan.eligible_bytes)
        self.assertEqual(1, len(reader.calls))
        self.assertEqual(0, reader.calls[0]["after_sequence"])
        self.assertEqual(checkpoint.audit_anchor_sequence, reader.calls[0]["through_sequence"])

    def test_cloud_logging_refusal_does_not_call_reader(self):
        checkpoint = self.checkpoint()
        reader = RecordingReader([])
        plan = plan_cloud_logging_retention(
            checkpoint,
            reader,
            audit_integrity_state="unbound_legacy",
        )
        self.assertFalse(plan.safe_to_compact)
        self.assertEqual([], reader.calls)


if __name__ == "__main__":
    unittest.main()

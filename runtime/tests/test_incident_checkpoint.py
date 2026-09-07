import json
import tempfile
import unittest
from pathlib import Path

from incident_checkpoint import JsonCheckpointStore, checkpoint_document
from incident_service import IncidentService, MemoryAuditLog
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
        self.calls = []

    def recover_uplink(self, production_id, uplink):
        self.calls.append((production_id, uplink))
        return ActionResult(True, "provider detail must not survive checkpoint", {"endpoint": "secret"})


def diagnosed():
    return [4.0, 18.0, 41.0, 37.0, 0.2, 0.1]


def recovery():
    return [0.2, 0.2, 0.1, 0.1]


class IncidentCheckpointTests(unittest.TestCase):
    def service(self, metrics, remediation, store):
        return IncidentService(
            SequenceMetrics(metrics), remediation, MemoryAuditLog(),
            checkpoint_store=store,
            clock_ms=lambda: 123456789,
            id_factory=lambda: "incident-001",
            recovery_sleep=lambda _: None,
        )

    def test_approved_revision_can_resume_once_after_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            store = JsonCheckpointStore(Path(directory) / "checkpoint.json")
            first_action = FakeRemediation()
            first = self.service(diagnosed(), first_action, store)
            snapshot = first.investigate()
            first.approve(incident_id=snapshot.incident_id, revision=snapshot.revision, approved_by="operator@example.com")
            self.assertEqual([], first_action.calls)

            second_action = FakeRemediation()
            restored = self.service(recovery(), second_action, store)
            self.assertEqual(snapshot.revision, restored.status().revision)
            self.assertIsNotNone(restored.status().approval)
            final = restored.execute_approved()
            self.assertEqual("recovered", final.outcome.status)
            self.assertEqual(1, len(second_action.calls))

            third = self.service([], FakeRemediation(), store)
            with self.assertRaises(RuntimeError):
                third.execute_approved()

    def test_fresh_investigation_invalidates_restored_approval(self):
        with tempfile.TemporaryDirectory() as directory:
            store = JsonCheckpointStore(Path(directory) / "checkpoint.json")
            service = self.service(diagnosed() + diagnosed(), FakeRemediation(), store)
            first = service.investigate()
            service.approve(incident_id=first.incident_id, revision=first.revision, approved_by="operator@example.com")
            refreshed = service.investigate()
            self.assertIsNone(refreshed.approval)

            restored = self.service([], FakeRemediation(), store)
            self.assertIsNone(restored.status().approval)
            with self.assertRaises(RuntimeError):
                restored.execute_approved()

    def test_tampered_checkpoint_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "checkpoint.json"
            store = JsonCheckpointStore(path)
            service = self.service(diagnosed(), FakeRemediation(), store)
            service.investigate()
            document = json.loads(path.read_text())
            document["state"]["revision"] = "0" * 16
            path.write_text(json.dumps(document))
            with self.assertRaises(ValueError):
                self.service([], FakeRemediation(), store)

    def test_provider_metadata_is_not_persisted(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "checkpoint.json"
            store = JsonCheckpointStore(path)
            service = self.service(diagnosed() + recovery(), FakeRemediation(), store)
            snapshot = service.investigate()
            service.approve(incident_id=snapshot.incident_id, revision=snapshot.revision, approved_by="operator@example.com")
            service.execute_approved()
            raw = path.read_text()
            self.assertNotIn("endpoint", raw)
            self.assertNotIn("provider detail", raw)
            restored = store.load()
            self.assertEqual({}, restored.outcome.action_result.metadata)
            self.assertEqual("restored checkpoint", restored.outcome.action_result.detail)

    def test_checkpoint_document_is_bounded_and_versioned(self):
        with tempfile.TemporaryDirectory() as directory:
            store = JsonCheckpointStore(Path(directory) / "checkpoint.json")
            service = self.service(diagnosed(), FakeRemediation(), store)
            service.investigate()
            checkpoint = store.load()
            document = checkpoint_document(checkpoint)
            self.assertEqual("stageguard.incident-checkpoint.v1", document["schema"])
            self.assertEqual(64, len(document["sha256"]))


if __name__ == "__main__":
    unittest.main()

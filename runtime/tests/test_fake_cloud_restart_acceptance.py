from pathlib import Path
import copy
import os
import re
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from api import _audit_integrity_policy_satisfied
from bootstrap import build_runtime
from cloud_audit import GoogleCloudLoggingAuditSink
from durable_audit_reader import GoogleCloudAuditReader
from incident_checkpoint import GoogleCloudStorageCheckpointStore
from remediation import ActionResult


class FakeMetrics:
    datasource_uid = "prom-main"

    def __init__(self, values):
        self.values = list(values)
        self.index = 0
        self.closed = False

    def instant(self, _promql):
        if self.index >= len(self.values):
            raise AssertionError("unexpected metric query")
        value = self.values[self.index]
        self.index += 1
        return value

    def close(self):
        self.closed = True


class CountingRemediation:
    def __init__(self):
        self.calls = 0

    def recover_uplink(self, _production_id, _uplink):
        self.calls += 1
        return ActionResult(True, "ok", {})


class FakePreconditionFailed(RuntimeError):
    code = 412


class FakeBlob:
    def __init__(self, bucket, name):
        self._bucket = bucket
        self._name = name
        self.generation = None

    def exists(self):
        return self._name in self._bucket.objects

    def reload(self):
        state = self._bucket.objects[self._name]
        self.generation = state["generation"]

    def download_as_bytes(self, *, if_generation_match):
        state = self._bucket.objects[self._name]
        if state["generation"] != if_generation_match:
            raise FakePreconditionFailed("generation mismatch")
        self.generation = state["generation"]
        return state["content"]

    def upload_from_string(self, content, *, content_type, if_generation_match):
        del content_type
        current = self._bucket.objects.get(self._name)
        generation = 0 if current is None else current["generation"]
        if generation != if_generation_match:
            raise FakePreconditionFailed("generation mismatch")
        next_generation = generation + 1
        self._bucket.objects[self._name] = {
            "generation": next_generation,
            "content": bytes(content),
        }
        self.generation = next_generation


class FakeBucket:
    def __init__(self):
        self.objects = {}

    def blob(self, name):
        return FakeBlob(self, name)


class FakeCloudLogger:
    full_name = "projects/media-prod/logs/stageguard-prod-audit"

    def __init__(self):
        self.documents = []

    def log_struct(self, info, *, severity="NOTICE"):
        del severity
        self.documents.append(copy.deepcopy(dict(info)))

    def list_entries(self, *, filter_=None, order_by=None, max_results=None, page_size=None):
        del order_by, page_size
        lower = 0
        upper = None
        lower_match = re.search(r"jsonPayload\.sequence>(\d+)", filter_ or "")
        upper_match = re.search(r"jsonPayload\.sequence<=(\d+)", filter_ or "")
        incident_match = re.search(r'jsonPayload\.incident_id="([^"]+)"', filter_ or "")
        if lower_match:
            lower = int(lower_match.group(1))
        if upper_match:
            upper = int(upper_match.group(1))
        incident_id = None if incident_match is None else incident_match.group(1)

        selected = []
        for document in self.documents:
            sequence = int(document["sequence"])
            if sequence <= lower or (upper is not None and sequence > upper):
                continue
            if incident_id is not None and document["incident_id"] != incident_id:
                continue
            selected.append(SimpleNamespace(payload=copy.deepcopy(document)))
        selected.sort(key=lambda entry: (entry.payload["sequence"], entry.payload["timestamp_unix_ms"]))
        return selected[:max_results] if max_results is not None else selected


def diagnosed_with_recovery():
    return [4.0, 18.0, 41.0, 37.0, 0.2, 0.1, 0.1, 0.1, 0.1, 0.1]


class FakeCloudRestartAcceptanceTests(unittest.TestCase):
    def test_production_bootstrap_restores_authenticated_winner_without_replay(self):
        example = Path(__file__).parents[1] / "telemetry.example.json"
        bucket = FakeBucket()
        logger = FakeCloudLogger()
        signing_key = b"s" * 32
        env = {
            "STAGEGUARD_CHECKPOINT_BUCKET": "stageguard-state-prod",
            "STAGEGUARD_CHECKPOINT_HMAC_KEY": "s" * 32,
            "GOOGLE_CLOUD_PROJECT": "media-prod",
        }

        def checkpoint_ctor(**kwargs):
            self.assertEqual("stageguard-state-prod", kwargs["bucket_name"])
            self.assertEqual("s" * 32, kwargs["signing_key"])
            self.assertEqual("media-prod", kwargs["project"])
            return GoogleCloudStorageCheckpointStore(
                bucket,
                signing_key,
                object_name=kwargs["object_name"],
            )

        def sink_ctor(**kwargs):
            self.assertEqual("media-prod", kwargs["project"])
            self.assertEqual("stageguard-prod-audit", kwargs["log_name"])
            return GoogleCloudLoggingAuditSink(logger)

        def reader_ctor(**kwargs):
            self.assertEqual("media-prod", kwargs["project"])
            self.assertEqual("stageguard-prod-audit", kwargs["log_name"])
            return GoogleCloudAuditReader(logger)

        first_remediation = CountingRemediation()
        with patch.dict(os.environ, env, clear=False), \
             patch("bootstrap.GoogleCloudStorageCheckpointStore.from_environment", side_effect=checkpoint_ctor), \
             patch("bootstrap.GoogleCloudLoggingAuditSink.from_environment", side_effect=sink_ctor), \
             patch("bootstrap.GoogleCloudAuditReader.from_environment", side_effect=reader_ctor):
            first = build_runtime(
                telemetry_config=example,
                activation_path=None,
                audit_path="unused.jsonl",
                host="127.0.0.1",
                port=0,
                audit_backend="cloud-logging",
                cloud_log_name="stageguard-prod-audit",
                checkpoint_backend="gcs",
                checkpoint_object="prod/current.json",
                audit_integrity_policy="require_verified",
                audit_anchor_interval=3,
                metrics_factory=lambda: FakeMetrics(diagnosed_with_recovery()),
                remediation_factory=lambda _profile: first_remediation,
            )
            try:
                investigated = first.service.investigate(actor="fake-cloud-test")
                first.service.approve(
                    incident_id=investigated.incident_id,
                    revision=investigated.revision,
                    approved_by="fake-cloud-operator",
                )
                completed = first.service.execute_approved(actor="fake-cloud-test")
                self.assertEqual("recovered", completed.outcome.status)
                self.assertEqual(1, first_remediation.calls)
                self.assertEqual("verified", first.service.audit_integrity_state())
                anchor = first.service.audit_anchor_state()
                head_sequence = first.service._audit_chain.sequence
                self.assertGreater(anchor["sequence"], 0)
                self.assertGreater(head_sequence, anchor["sequence"])
                incident_id = completed.incident_id
            finally:
                first.close()

        suffix = [
            document for document in logger.documents
            if document["incident_id"] == incident_id and document["sequence"] > anchor["sequence"]
        ]
        self.assertTrue(suffix)
        competitor = copy.deepcopy(suffix[0])
        competitor["actor"] = "losing-writer"
        competitor["payload"] = dict(competitor["payload"])
        competitor["payload"]["writer_branch"] = "loser"
        logger.documents.append(competitor)

        restarted_remediation = CountingRemediation()
        with patch.dict(os.environ, env, clear=False), \
             patch("bootstrap.GoogleCloudStorageCheckpointStore.from_environment", side_effect=checkpoint_ctor), \
             patch("bootstrap.GoogleCloudLoggingAuditSink.from_environment", side_effect=sink_ctor), \
             patch("bootstrap.GoogleCloudAuditReader.from_environment", side_effect=reader_ctor):
            restarted = build_runtime(
                telemetry_config=example,
                activation_path=None,
                audit_path="unused.jsonl",
                host="127.0.0.1",
                port=0,
                audit_backend="cloud-logging",
                cloud_log_name="stageguard-prod-audit",
                checkpoint_backend="gcs",
                checkpoint_object="prod/current.json",
                audit_integrity_policy="require_verified",
                audit_anchor_interval=3,
                metrics_factory=lambda: FakeMetrics([]),
                remediation_factory=lambda _profile: restarted_remediation,
            )
            try:
                restored = restarted.service.status()
                self.assertIsNotNone(restored)
                self.assertEqual("recovered", restored.outcome.status)
                self.assertEqual("verified", restarted.service.audit_integrity_state())
                self.assertEqual("synchronized", restarted.service.checkpoint_state())
                self.assertEqual("clear", restarted.service.execution_reconciliation_state())
                self.assertEqual("require_verified", restarted.service._audit_integrity_policy)
                self.assertTrue(_audit_integrity_policy_satisfied(restarted.service))
                self.assertEqual(0, restarted_remediation.calls)
                with self.assertRaisesRegex(RuntimeError, "already been consumed"):
                    restarted.service.execute_approved(actor="fake-cloud-test")
                self.assertEqual(0, restarted_remediation.calls)
            finally:
                restarted.close()


if __name__ == "__main__":
    unittest.main()

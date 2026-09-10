from __future__ import annotations

import http.client
import json
import tempfile
import threading
import time
import unittest
from pathlib import Path

from anchored_execution_safety import AnchoredExecutionSafeIncidentService
from anchored_incident_service import AnchoredJsonlAuditLog
from api import make_server
from identity import StaticBearerIdentityProvider
from incident_checkpoint import JsonCheckpointStore
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


class FakeMonotonic:
    def __init__(self):
        self.value = 100.0
        self.lock = threading.Lock()

    def __call__(self):
        with self.lock:
            return self.value

    def advance(self, seconds):
        with self.lock:
            self.value += seconds


class BlockingRemediation:
    """Hold the provider call open so the HTTP concurrency contract is observable."""

    def __init__(self):
        self.entered = threading.Event()
        self.release = threading.Event()
        self.calls = 0

    def recover_uplink(self, _production_id, _uplink):
        self.calls += 1
        self.entered.set()
        if not self.release.wait(timeout=3.0):
            raise RuntimeError("test remediation release timed out")
        return ActionResult(True, "ok", {})


def diagnosed_and_recovery_metrics():
    # Six investigation queries, then two recovery samples with two queries each.
    return [4.0, 18.0, 41.0, 37.0, 0.2, 0.1, 0.2, 0.2, 0.1, 0.1]


class ApiConcurrencyTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        self.remediation = BlockingRemediation()
        self.monotonic = FakeMonotonic()
        self.service = AnchoredExecutionSafeIncidentService(
            SequenceMetrics(diagnosed_and_recovery_metrics()),
            self.remediation,
            AnchoredJsonlAuditLog(root / "audit.jsonl"),
            checkpoint_store=JsonCheckpointStore(root / "checkpoint.json"),
            clock_ms=lambda: 123456789,
            id_factory=lambda: "incident-api-concurrency-001",
            recovery_sleep=lambda _: None,
            execution_max_seconds=5.0,
            monotonic=self.monotonic,
        )
        self.provider = StaticBearerIdentityProvider({"operator-secret": "operator@example.com"})
        self.server = make_server(self.service, "127.0.0.1", 0, identity_provider=self.provider)
        self.server_thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.server_thread.start()
        self.port = self.server.server_address[1]

        investigated = self.service.investigate(actor="operator@example.com")
        self.approved = self.service.approve(
            incident_id=investigated.incident_id,
            revision=investigated.revision,
            approved_by="operator@example.com",
        )

    def tearDown(self):
        self.remediation.release.set()
        self.server.shutdown()
        self.server.server_close()
        self.server_thread.join(timeout=2.0)
        self.directory.cleanup()

    def request(self, method, path, payload=None, *, token="operator-secret", timeout=1.0):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=timeout)
        headers = {}
        if token is not None:
            headers["Authorization"] = f"Bearer {token}"
        body = None
        if payload is not None:
            body = json.dumps(payload)
            headers["Content-Type"] = "application/json"
        started = time.monotonic()
        try:
            connection.request(method, path, body=body, headers=headers)
            response = connection.getresponse()
            raw = response.read().decode("utf-8")
            elapsed = time.monotonic() - started
            return response.status, raw, elapsed
        finally:
            connection.close()

    def test_execute_keeps_http_reads_responsive_and_competing_mutations_fail_closed(self):
        execute_result = {}
        execute_errors = []

        def execute_request():
            try:
                execute_result["response"] = self.request(
                    "POST",
                    "/v1/execute",
                    {},
                    timeout=4.0,
                )
            except Exception as exc:  # pragma: no cover - surfaced below with context
                execute_errors.append(exc)

        worker = threading.Thread(target=execute_request, daemon=True)
        worker.start()
        self.assertTrue(self.remediation.entered.wait(timeout=1.0), "HTTP execute did not reach provider fake")

        try:
            status, raw, elapsed = self.request("GET", "/v1/incident")
            self.assertEqual(200, status)
            self.assertLess(elapsed, 0.75, "incident status blocked behind provider/recovery I/O")
            lifecycle = json.loads(raw)
            self.assertEqual(self.approved.revision, lifecycle["incident"]["revision"])
            self.assertIsNone(lifecycle["incident"]["outcome"])
            self.assertEqual(
                {"active": True, "age_seconds": 0.0, "max_seconds": 5.0, "deadline_exceeded": False},
                lifecycle["remediation_execution"],
            )

            status, raw, elapsed = self.request("GET", "/readyz", token=None)
            self.assertIn(status, {200, 503})
            self.assertLess(elapsed, 0.75, "readiness blocked behind provider/recovery I/O")
            readiness = json.loads(raw)
            self.assertEqual("dispatching", readiness["checks"]["remediation_execution_phase"])
            self.assertEqual("ok", readiness["checks"]["remediation_execution_deadline"])

            status, raw, elapsed = self.request("GET", "/metrics", token=None)
            self.assertEqual(200, status)
            self.assertLess(elapsed, 0.75, "metrics blocked behind provider/recovery I/O")
            self.assertIn('stageguard_remediation_execution_phase{phase="dispatching"} 1', raw)
            self.assertIn("stageguard_remediation_execution_active 1", raw)
            self.assertIn("stageguard_remediation_execution_age_seconds 0.0", raw)
            self.assertIn("stageguard_remediation_execution_max_seconds 5.0", raw)
            self.assertIn("stageguard_remediation_execution_deadline_exceeded 0", raw)

            self.monotonic.advance(6.0)
            status, raw, elapsed = self.request("GET", "/readyz", token=None)
            self.assertEqual(503, status)
            self.assertLess(elapsed, 0.75, "deadline readiness blocked behind provider/recovery I/O")
            readiness = json.loads(raw)
            self.assertEqual("exceeded", readiness["checks"]["remediation_execution_deadline"])
            self.assertEqual("execution_uncertain", readiness["checks"]["checkpoint"])

            status, raw, elapsed = self.request("GET", "/metrics", token=None)
            self.assertEqual(200, status)
            self.assertLess(elapsed, 0.75, "deadline metrics blocked behind provider/recovery I/O")
            self.assertIn("stageguard_remediation_execution_active 1", raw)
            self.assertIn("stageguard_remediation_execution_age_seconds 6.0", raw)
            self.assertIn("stageguard_remediation_execution_max_seconds 5.0", raw)
            self.assertIn("stageguard_remediation_execution_deadline_exceeded 1", raw)

            status, raw, elapsed = self.request("POST", "/v1/investigate", {})
            self.assertEqual(409, status)
            self.assertLess(elapsed, 0.75, "competing investigation queued behind active execution")
            self.assertIn("already in progress", json.loads(raw)["detail"])

            status, raw, elapsed = self.request("POST", "/v1/execute", {})
            self.assertEqual(409, status)
            self.assertLess(elapsed, 0.75, "competing execution queued behind active execution")
            self.assertIn("already in progress", json.loads(raw)["detail"])
            self.assertEqual(1, self.remediation.calls, "HTTP concurrency must never replay remediation")
        finally:
            self.remediation.release.set()

        worker.join(timeout=2.0)
        self.assertFalse(worker.is_alive(), "original execute request did not finish")
        self.assertEqual([], execute_errors)
        status, raw, _elapsed = execute_result["response"]
        self.assertEqual(200, status)
        completed = json.loads(raw)
        self.assertEqual("recovered", completed["incident"]["outcome"]["status"])
        self.assertEqual("resolved", self.service.execution_checkpoint_phase())
        self.assertEqual(1, self.remediation.calls)

        status, raw, _elapsed = self.request("GET", "/metrics", token=None)
        self.assertEqual(200, status)
        self.assertIn("stageguard_remediation_execution_active 0", raw)
        self.assertIn("stageguard_remediation_execution_age_seconds 0.0", raw)
        self.assertIn("stageguard_remediation_execution_deadline_exceeded 0", raw)


if __name__ == "__main__":
    unittest.main()

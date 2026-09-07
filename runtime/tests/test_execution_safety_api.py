import http.client
import json
import threading
import unittest

from api import make_server
from execution_safety import ExecutionSafeIncidentService
from identity import StaticBearerIdentityProvider
from incident_checkpoint import CheckpointConflictError, IncidentCheckpoint
from incident_service import MemoryAuditLog
from remediation import ActionResult


class SequenceMetrics:
    datasource_uid = "prometheus"

    def __init__(self, values):
        self.values = list(values)
        self.index = 0

    def instant(self, _query):
        if self.index >= len(self.values):
            raise AssertionError("unexpected metric query")
        value = self.values[self.index]
        self.index += 1
        return value


class ConflictStore:
    def __init__(self):
        self.current = None
        self.fail_next_save = False

    def load(self):
        return self.current

    def save(self, checkpoint: IncidentCheckpoint):
        if self.fail_next_save:
            self.fail_next_save = False
            raise CheckpointConflictError("bounded conflict")
        self.current = checkpoint


class ReconcilingRemediation:
    requires_operation_reconciliation = True

    def __init__(self):
        self.calls = []
        self.reconcile_calls = []

    def recover_uplink_idempotent(self, production_id, uplink, operation_id):
        self.calls.append((production_id, uplink, operation_id))
        return ActionResult(True, "accepted", {"operation_id": operation_id})

    def recover_uplink(self, production_id, uplink):
        raise AssertionError("idempotent execution required")

    def reconcile_operation(self, operation_id):
        self.reconcile_calls.append(operation_id)
        return "accepted"


class ReadyResult:
    def to_dict(self):
        return {
            "ready": True,
            "checks": {
                "metric_activation": "ready",
                "loki_activation": "not_configured",
                "prometheus_mcp": "ready",
                "loki_mcp": "not_configured",
            },
        }


class ReadyProbe:
    def check(self):
        return ReadyResult()

    def prometheus_metrics(self):
        return "stageguard_evidence_plane_ready 1\n"


def diagnosed():
    return [4.0, 18.0, 41.0, 37.0, 0.2, 0.1]


def recovery():
    return [0.2, 0.2, 0.1, 0.1]


class ExecutionSafetyApiTests(unittest.TestCase):
    def setUp(self):
        self.store = ConflictStore()
        self.remediation = ReconcilingRemediation()
        self.service = ExecutionSafeIncidentService(
            SequenceMetrics(diagnosed() + recovery() + diagnosed()),
            self.remediation,
            MemoryAuditLog(),
            checkpoint_store=self.store,
            clock_ms=lambda: 123456789,
            id_factory=lambda: "incident-001",
            recovery_sleep=lambda _: None,
        )
        snapshot = self.service.investigate()
        self.service.approve(
            incident_id=snapshot.incident_id,
            revision=snapshot.revision,
            approved_by="operator@example.com",
        )
        self.durable_winner = self.store.current
        self.store.fail_next_save = True
        with self.assertRaises(CheckpointConflictError):
            self.service.execute_approved(actor="operator@example.com")
        self.assertEqual(1, len(self.remediation.calls))

        self.service._readiness_probe = ReadyProbe()
        self.provider = StaticBearerIdentityProvider({"operator-secret": "operator@example.com"})
        self.server = make_server(self.service, "127.0.0.1", 0, identity_provider=self.provider)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.port = self.server.server_address[1]

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def request_json(self, method, path, payload=None, token=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=2)
        headers = {}
        body = None
        if token is not None:
            headers["Authorization"] = f"Bearer {token}"
        if payload is not None:
            body = json.dumps(payload)
            headers["Content-Type"] = "application/json"
        connection.request(method, path, body=body, headers=headers)
        response = connection.getresponse()
        data = json.loads(response.read().decode("utf-8"))
        connection.close()
        return response.status, data

    def request_text(self, path):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=2)
        connection.request("GET", path)
        response = connection.getresponse()
        data = response.read().decode("utf-8")
        connection.close()
        return response.status, data

    def test_execution_uncertainty_forces_not_ready_and_exports_bounded_gauge(self):
        status, body = self.request_json("GET", "/readyz")
        self.assertEqual(503, status)
        self.assertFalse(body["ready"])
        self.assertEqual("execution_uncertain", body["checks"]["checkpoint"])

        status, metrics = self.request_text("/metrics")
        self.assertEqual(200, status)
        self.assertIn("stageguard_remediation_execution_uncertain 1", metrics)
        self.assertNotIn(self.remediation.calls[0][2], metrics)

    def test_incident_endpoint_exposes_only_bounded_reconciliation_phase(self):
        status, body = self.request_json("GET", "/v1/incident", token="operator-secret")
        self.assertEqual(200, status)
        self.assertEqual("execution_uncertain", body["checkpoint_state"])
        self.assertEqual("reload_required", body["execution_reconciliation_state"])
        serialized = json.dumps(body)
        self.assertNotIn(self.remediation.calls[0][2], serialized)
        self.assertNotIn("accepted", serialized)
        self.assertNotIn("not_found", serialized)

    def test_incident_lifecycle_state_requires_authentication(self):
        status, body = self.request_json("GET", "/v1/incident")
        self.assertEqual(401, status)
        self.assertEqual("unauthorized", body["error"])
        self.assertNotIn("execution_reconciliation_state", body)

    def test_authenticated_reconciliation_requires_reload_and_never_replays_action(self):
        status, body = self.request_json(
            "POST", "/v1/execution/reconcile", {}, "operator-secret"
        )
        self.assertEqual(409, status)
        self.assertEqual("invalid_state", body["error"])
        self.assertEqual(1, len(self.remediation.calls))
        self.assertEqual([], self.remediation.reconcile_calls)

        self.store.current = self.durable_winner
        status, body = self.request_json(
            "POST", "/v1/checkpoint/reload", {}, "operator-secret"
        )
        self.assertEqual(200, status)
        self.assertEqual("execution_uncertain", body["checkpoint_state"])
        self.assertEqual("reloaded", body["execution_reconciliation_state"])
        self.assertIsNotNone(body["incident"]["approval"])
        self.assertEqual(1, len(self.remediation.calls))

        # A fresh GET after browser/process UI refresh must preserve the safe
        # recovery phase instead of forcing operators to infer it from errors.
        status, refreshed = self.request_json("GET", "/v1/incident", token="operator-secret")
        self.assertEqual(200, status)
        self.assertEqual("reloaded", refreshed["execution_reconciliation_state"])

        status, body = self.request_json(
            "POST", "/v1/execution/reconcile", {}, "operator-secret"
        )
        self.assertEqual(200, status)
        self.assertEqual("synchronized", body["checkpoint_state"])
        self.assertEqual("clear", body["execution_reconciliation_state"])
        self.assertIsNone(body["incident"]["approval"])
        self.assertIsNone(body["incident"]["outcome"])
        self.assertEqual(1, len(self.remediation.calls), "reconciliation must never replay remediation")
        self.assertEqual(1, len(self.remediation.reconcile_calls))

    def test_reconciliation_endpoint_is_authenticated_and_argument_free(self):
        status, body = self.request_json("POST", "/v1/execution/reconcile", {})
        self.assertEqual(401, status)
        self.assertEqual("unauthorized", body["error"])

        status, body = self.request_json(
            "POST",
            "/v1/execution/reconcile",
            {"operation_id": self.remediation.calls[0][2]},
            "operator-secret",
        )
        self.assertEqual(400, status)
        self.assertEqual("invalid_request", body["error"])
        self.assertEqual([], self.remediation.reconcile_calls)


if __name__ == "__main__":
    unittest.main()

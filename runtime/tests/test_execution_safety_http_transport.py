import io
import json
import unittest
import urllib.error
from unittest.mock import patch

from execution_safety import ExecutionSafeIncidentService
from http_remediation_transport import HttpRemediationTransport
from incident_checkpoint import CheckpointConflictError, IncidentCheckpoint
from incident_service import MemoryAuditLog
from production_remediation import AllowlistedProductionRemediationClient


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


class FakeHttpResponse:
    def __init__(self, status, document):
        self.status = status
        self.body = json.dumps(document, separators=(",", ":")).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, size=-1):
        return self.body[:size] if size >= 0 else self.body


def diagnosed():
    return [4.0, 18.0, 41.0, 37.0, 0.2, 0.1]


def recovery():
    return [0.2, 0.2, 0.1, 0.1]


class ConcreteHttpExecutionSafetyTests(unittest.TestCase):
    def _service(self):
        transport = HttpRemediationTransport(
            "https://writer.example.test/v1/remediate",
            "test-token",
            reconciliation_endpoint="https://reader.example.test/v1/operations",
        )
        remediation = AllowlistedProductionRemediationClient(
            transport,
            allowed_production_id="broadcast-demo",
            allowed_uplink="primary",
            max_attempts=1,
            retry_delay_seconds=0,
        )
        store = ConflictStore()
        service = ExecutionSafeIncidentService(
            SequenceMetrics(diagnosed() + recovery() + diagnosed()),
            remediation,
            MemoryAuditLog(),
            checkpoint_store=store,
            clock_ms=lambda: 123456789,
            id_factory=lambda: "incident-001",
            recovery_sleep=lambda _: None,
        )
        snapshot = service.investigate()
        service.approve(
            incident_id=snapshot.incident_id,
            revision=snapshot.revision,
            approved_by="operator@example.com",
        )
        return service, store

    @staticmethod
    def _request_method(request):
        return request.get_method()

    def _enter_uncertainty(self, service, store, requests):
        durable_winner = store.current

        def accepted_execution(request, timeout):
            requests.append((self._request_method(request), request.full_url, request.data, timeout))
            self.assertEqual("POST", request.get_method())
            payload = json.loads(request.data.decode("utf-8"))
            return FakeHttpResponse(
                200,
                {"accepted": True, "operation_id": payload["operation_id"]},
            )

        store.fail_next_save = True
        with patch("urllib.request.urlopen", side_effect=accepted_execution):
            with self.assertRaises(CheckpointConflictError):
                service.execute_approved()

        self.assertEqual(1, sum(method == "POST" for method, *_ in requests))
        self.assertEqual("execution_uncertain", service.checkpoint_state())
        store.current = durable_winner
        service.reload_checkpoint_after_conflict()
        self.assertEqual("reloaded", service.execution_reconciliation_state())

    def test_accepted_reconciliation_recovers_with_fresh_evidence_without_replay(self):
        service, store = self._service()
        requests = []
        self._enter_uncertainty(service, store, requests)

        def reconcile(request, timeout):
            requests.append((request.get_method(), request.full_url, request.data, timeout))
            self.assertEqual("GET", request.get_method())
            self.assertIsNone(request.data)
            operation_id = request.full_url.rsplit("/", 1)[-1]
            return FakeHttpResponse(200, {"operation_id": operation_id, "state": "accepted"})

        with patch("urllib.request.urlopen", side_effect=reconcile):
            refreshed = service.reconcile_execution_uncertainty(actor="operator@example.com")

        self.assertIsNone(refreshed.approval)
        self.assertIsNone(refreshed.outcome)
        self.assertEqual("clear", service.execution_reconciliation_state())
        self.assertEqual(1, sum(method == "POST" for method, *_ in requests))
        self.assertEqual(1, sum(method == "GET" for method, *_ in requests))

    def test_not_found_reconciliation_is_bounded_and_never_replays(self):
        service, store = self._service()
        requests = []
        self._enter_uncertainty(service, store, requests)

        def reconcile_404(request, timeout):
            requests.append((request.get_method(), request.full_url, request.data, timeout))
            raise urllib.error.HTTPError(request.full_url, 404, "missing", {}, io.BytesIO(b"provider detail"))

        with patch("urllib.request.urlopen", side_effect=reconcile_404):
            refreshed = service.reconcile_execution_uncertainty()

        self.assertIsNone(refreshed.approval)
        self.assertEqual("clear", service.execution_reconciliation_state())
        self.assertEqual(1, sum(method == "POST" for method, *_ in requests))
        self.assertEqual(1, sum(method == "GET" for method, *_ in requests))

    def test_timeout_keeps_uncertainty_blocked_and_does_not_replay(self):
        service, store = self._service()
        requests = []
        self._enter_uncertainty(service, store, requests)

        def timeout_lookup(request, timeout):
            requests.append((request.get_method(), request.full_url, request.data, timeout))
            raise TimeoutError("provider internals")

        with patch("urllib.request.urlopen", side_effect=timeout_lookup):
            with self.assertRaisesRegex(RuntimeError, "idempotency state is unresolved"):
                service.reconcile_execution_uncertainty()

        self.assertEqual("execution_uncertain", service.checkpoint_state())
        self.assertEqual("reloaded", service.execution_reconciliation_state())
        self.assertEqual(1, sum(method == "POST" for method, *_ in requests))
        self.assertEqual(1, sum(method == "GET" for method, *_ in requests))

    def test_malformed_provider_response_keeps_uncertainty_blocked(self):
        service, store = self._service()
        requests = []
        self._enter_uncertainty(service, store, requests)

        def malformed_lookup(request, timeout):
            requests.append((request.get_method(), request.full_url, request.data, timeout))
            return FakeHttpResponse(200, {"state": "accepted", "provider_debug": "must-not-escape"})

        with patch("urllib.request.urlopen", side_effect=malformed_lookup):
            with self.assertRaisesRegex(RuntimeError, "idempotency state is unresolved") as raised:
                service.reconcile_execution_uncertainty()

        self.assertNotIn("provider_debug", str(raised.exception))
        self.assertEqual("execution_uncertain", service.checkpoint_state())
        self.assertEqual(1, sum(method == "POST" for method, *_ in requests))

    def test_repeated_reconciliation_after_success_performs_no_network_and_no_replay(self):
        service, store = self._service()
        requests = []
        self._enter_uncertainty(service, store, requests)

        def reconcile(request, timeout):
            requests.append((request.get_method(), request.full_url, request.data, timeout))
            operation_id = request.full_url.rsplit("/", 1)[-1]
            return FakeHttpResponse(200, {"operation_id": operation_id, "state": "accepted"})

        with patch("urllib.request.urlopen", side_effect=reconcile):
            service.reconcile_execution_uncertainty()

        with patch("urllib.request.urlopen") as network:
            with self.assertRaisesRegex(RuntimeError, "no uncertain remediation execution"):
                service.reconcile_execution_uncertainty()
            network.assert_not_called()

        self.assertEqual(1, sum(method == "POST" for method, *_ in requests))
        self.assertEqual(1, sum(method == "GET" for method, *_ in requests))


if __name__ == "__main__":
    unittest.main()

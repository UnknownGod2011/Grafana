from __future__ import annotations

import json
import multiprocessing
import os
import shutil
import signal
import ssl
import subprocess
import tempfile
import threading
import unittest
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from execution_safety import ExecutionSafeIncidentService
from http_remediation_transport import HttpRemediationTransport
from incident_checkpoint import JsonCheckpointStore
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


class NoopProductionRemediation:
    requires_operation_reconciliation = True

    def recover_uplink_idempotent(self, production_id, uplink, operation_id):
        raise AssertionError("setup must not execute remediation")

    def reconcile_operation(self, operation_id):
        return "not_found"


def diagnosed():
    return [4.0, 18.0, 41.0, 37.0, 0.2, 0.1]


def build_service(store, remediation, values):
    return ExecutionSafeIncidentService(
        SequenceMetrics(values),
        remediation,
        MemoryAuditLog(),
        checkpoint_store=store,
        clock_ms=lambda: 123456789,
        id_factory=lambda: "incident-http-subprocess-001",
        recovery_sleep=lambda _: None,
    )


def hard_kill():
    os.kill(os.getpid(), signal.SIGKILL)
    os._exit(93)


def insecure_test_urlopen(request, *, timeout):
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    return urllib.request.urlopen(request, timeout=timeout, context=context)


class CrashBoundaryTransport:
    """Wrap the concrete HTTPS transport and kill at the requested boundary."""

    def __init__(self, inner, checkpoint_path, crash_mode):
        self.inner = inner
        self.checkpoint_path = checkpoint_path
        self.crash_mode = crash_mode

    def execute(self, request, *, timeout_seconds):
        checkpoint = JsonCheckpointStore(self.checkpoint_path).load()
        if checkpoint is None or checkpoint.execution_phase != "dispatching":
            os._exit(90)
        if self.crash_mode == "after_dispatching_before_http_post":
            hard_kill()
        if self.crash_mode != "after_http_acceptance":
            os._exit(91)
        result = self.inner.execute(request, timeout_seconds=timeout_seconds)
        if not result.accepted:
            os._exit(92)
        hard_kill()

    def reconcile(self, operation_id, *, timeout_seconds):
        return self.inner.reconcile(operation_id, timeout_seconds=timeout_seconds)


class ProviderHandler(BaseHTTPRequestHandler):
    server_version = "StageGuardCrashProvider/1"

    def log_message(self, _format, *_args):
        return

    def _json(self, status, document):
        body = json.dumps(document, sort_keys=True, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path != "/v1/recover":
            self._json(404, {"error": "not found"})
            return
        length = int(self.headers.get("Content-Length", "0"))
        document = json.loads(self.rfile.read(length).decode("utf-8"))
        operation_id = document["operation_id"]
        self.server.events.append(("POST", operation_id, self.headers.get("Idempotency-Key"), length))
        self.server.accepted.add(operation_id)
        self._json(200, {"accepted": True, "operation_id": operation_id})

    def do_GET(self):
        prefix = "/v1/operations/"
        if not self.path.startswith(prefix):
            self._json(404, {"error": "not found"})
            return
        operation_id = self.path[len(prefix):]
        self.server.events.append(("GET", operation_id, None, 0))
        if operation_id not in self.server.accepted:
            self._json(404, {"error": "not found"})
            return
        self._json(200, {"operation_id": operation_id, "state": "accepted"})


def crash_child(checkpoint_path, endpoint, reconciliation_endpoint, crash_mode):
    inner = HttpRemediationTransport(
        endpoint,
        "test-only-bearer",
        reconciliation_endpoint,
        urlopen=insecure_test_urlopen,
    )
    transport = CrashBoundaryTransport(inner, checkpoint_path, crash_mode)
    remediation = AllowlistedProductionRemediationClient(
        transport,
        allowed_production_id="broadcast-alpha",
        allowed_uplink="uplink-b",
        max_attempts=1,
    )
    service = build_service(JsonCheckpointStore(checkpoint_path), remediation, [])
    service.execute_approved(actor="subprocess-operator@example.com")
    os._exit(94)


@unittest.skipUnless(hasattr(signal, "SIGKILL"), "requires POSIX SIGKILL semantics")
@unittest.skipUnless(shutil.which("openssl"), "requires openssl to create an ephemeral test certificate")
class HttpSubprocessCrashRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        cert = root / "cert.pem"
        key = root / "key.pem"
        subprocess.run(
            [
                shutil.which("openssl"),
                "req",
                "-x509",
                "-newkey",
                "rsa:2048",
                "-nodes",
                "-keyout",
                str(key),
                "-out",
                str(cert),
                "-days",
                "1",
                "-subj",
                "/CN=localhost",
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), ProviderHandler)
        self.server.events = []
        self.server.accepted = set()
        server_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        server_context.load_cert_chain(certfile=str(cert), keyfile=str(key))
        self.server.socket = server_context.wrap_socket(self.server.socket, server_side=True)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        port = self.server.server_address[1]
        self.endpoint = f"https://127.0.0.1:{port}/v1/recover"
        self.reconciliation_endpoint = f"https://127.0.0.1:{port}/v1/operations"
        self.checkpoint_path = str(root / "incident.json")

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        self.tmp.cleanup()

    def prepare_approved_checkpoint(self):
        store = JsonCheckpointStore(self.checkpoint_path)
        service = build_service(store, NoopProductionRemediation(), diagnosed())
        snapshot = service.investigate(actor="setup@example.com")
        service.approve(
            incident_id=snapshot.incident_id,
            revision=snapshot.revision,
            approved_by="operator@example.com",
        )
        self.assertEqual("approved", store.load().execution_phase)

    def production_client(self):
        transport = HttpRemediationTransport(
            self.endpoint,
            "test-only-bearer",
            self.reconciliation_endpoint,
            urlopen=insecure_test_urlopen,
        )
        return AllowlistedProductionRemediationClient(
            transport,
            allowed_production_id="broadcast-alpha",
            allowed_uplink="uplink-b",
            max_attempts=1,
        )

    def run_case(self, crash_mode, expected_posts):
        self.prepare_approved_checkpoint()
        context = multiprocessing.get_context("spawn")
        process = context.Process(
            target=crash_child,
            args=(self.checkpoint_path, self.endpoint, self.reconciliation_endpoint, crash_mode),
        )
        process.start()
        process.join(10)
        if process.is_alive():
            process.kill()
            process.join(5)
            self.fail("crash child did not terminate at the intended HTTP boundary")
        self.assertEqual(-signal.SIGKILL, process.exitcode)

        durable = JsonCheckpointStore(self.checkpoint_path).load()
        self.assertEqual("dispatching", durable.execution_phase)
        posts = [event for event in self.server.events if event[0] == "POST"]
        self.assertEqual(expected_posts, len(posts))
        if posts:
            self.assertEqual(posts[0][1], posts[0][2], "Idempotency-Key must equal deterministic operation id")
            self.assertGreater(posts[0][3], 0)

        restarted = build_service(
            JsonCheckpointStore(self.checkpoint_path),
            self.production_client(),
            diagnosed(),
        )
        self.assertEqual("execution_uncertain", restarted.checkpoint_state())
        refreshed = restarted.reconcile_execution_uncertainty(actor="operator@example.com")
        self.assertIsNone(refreshed.approval)
        self.assertEqual("synchronized", restarted.checkpoint_state())
        self.assertEqual("none", restarted.execution_checkpoint_phase())

        # Reconciliation is read-only and recovery must not replay the POST.
        posts_after = [event for event in self.server.events if event[0] == "POST"]
        gets_after = [event for event in self.server.events if event[0] == "GET"]
        self.assertEqual(expected_posts, len(posts_after))
        self.assertEqual(1, len(gets_after))
        self.assertEqual(0, gets_after[0][3])
        if expected_posts:
            self.assertEqual(posts_after[0][1], gets_after[0][1])

        # Another restart still has no approval and therefore no executable stale action.
        final_restart = build_service(
            JsonCheckpointStore(self.checkpoint_path),
            self.production_client(),
            [],
        )
        self.assertEqual("synchronized", final_restart.checkpoint_state())
        self.assertIsNone(final_restart.status().approval)
        self.assertEqual(expected_posts, len([event for event in self.server.events if event[0] == "POST"]))

    def test_sigkill_after_dispatching_before_http_post_never_executes(self):
        self.run_case("after_dispatching_before_http_post", expected_posts=0)

    def test_sigkill_after_http_acceptance_reconciles_without_second_post(self):
        self.run_case("after_http_acceptance", expected_posts=1)


if __name__ == "__main__":
    unittest.main()

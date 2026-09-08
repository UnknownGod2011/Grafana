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
import time
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path

from api import _service_readiness
from incident_checkpoint import JsonCheckpointStore
from tests.test_http_subprocess_crash_recovery import (
    ProviderHandler,
    build_service,
    crash_child,
    diagnosed,
    insecure_test_urlopen,
)
from http_remediation_transport import HttpRemediationTransport
from production_remediation import AllowlistedProductionRemediationClient


class AmbiguousProviderHandler(ProviderHandler):
    """Provider with switchable read-only reconciliation failure modes."""

    def do_GET(self):
        prefix = "/v1/operations/"
        if not self.path.startswith(prefix):
            self._json(404, {"error": "not found"})
            return

        operation_id = self.path[len(prefix):]
        self.server.events.append(("GET", operation_id, None, 0))
        mode = self.server.reconciliation_mode

        if mode == "timeout":
            time.sleep(self.server.timeout_delay_seconds)
            try:
                self._json(200, {"operation_id": operation_id, "state": "accepted"})
            except (BrokenPipeError, ConnectionResetError, ssl.SSLError):
                pass
            return
        if mode == "malformed":
            body = b"{not-json"
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if mode == "wrong_operation_id":
            self._json(200, {"operation_id": "sg-" + "0" * 40, "state": "accepted"})
            return
        if mode == "unknown_state":
            self._json(200, {"operation_id": operation_id, "state": "pending"})
            return
        if mode != "normal":
            self._json(500, {"error": "invalid test mode"})
            return

        if operation_id not in self.server.accepted:
            self._json(404, {"error": "not found"})
            return
        self._json(200, {"operation_id": operation_id, "state": "accepted"})


class _ReadinessResult:
    def to_dict(self):
        return {"ready": True, "checks": {"grafana_evidence": "ok"}}


class AlwaysReadyEvidenceProbe:
    """Isolate lifecycle readiness from external MCP availability in this test."""

    def check(self):
        return _ReadinessResult()


@unittest.skipUnless(hasattr(signal, "SIGKILL"), "requires POSIX SIGKILL semantics")
@unittest.skipUnless(shutil.which("openssl"), "requires openssl to create an ephemeral test certificate")
class HttpSubprocessReconciliationAmbiguityTests(unittest.TestCase):
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

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), AmbiguousProviderHandler)
        self.server.events = []
        self.server.accepted = set()
        self.server.reconciliation_mode = "normal"
        self.server.timeout_delay_seconds = 0.35
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
            timeout_seconds=0.1,
            max_attempts=1,
        )

    def prepare_approved_checkpoint(self):
        from tests.test_http_subprocess_crash_recovery import NoopProductionRemediation

        store = JsonCheckpointStore(self.checkpoint_path)
        service = build_service(store, NoopProductionRemediation(), diagnosed())
        snapshot = service.investigate(actor="setup@example.com")
        service.approve(
            incident_id=snapshot.incident_id,
            revision=snapshot.revision,
            approved_by="operator@example.com",
        )
        self.assertEqual("approved", store.load().execution_phase)

    def crash_after_provider_acceptance(self):
        self.prepare_approved_checkpoint()
        context = multiprocessing.get_context("spawn")
        process = context.Process(
            target=crash_child,
            args=(
                self.checkpoint_path,
                self.endpoint,
                self.reconciliation_endpoint,
                "after_http_acceptance",
            ),
        )
        process.start()
        process.join(10)
        if process.is_alive():
            process.kill()
            process.join(5)
            self.fail("crash child did not terminate after provider acceptance")
        self.assertEqual(-signal.SIGKILL, process.exitcode)
        self.assertEqual("dispatching", JsonCheckpointStore(self.checkpoint_path).load().execution_phase)
        posts = [event for event in self.server.events if event[0] == "POST"]
        self.assertEqual(1, len(posts))
        self.assertEqual(posts[0][1], posts[0][2])

    def assert_fail_closed_then_recovers(self, mode):
        self.crash_after_provider_acceptance()
        self.server.reconciliation_mode = mode

        restarted = build_service(
            JsonCheckpointStore(self.checkpoint_path),
            self.production_client(),
            diagnosed(),
        )
        restarted._readiness_probe = AlwaysReadyEvidenceProbe()
        self.assertEqual("execution_uncertain", restarted.checkpoint_state())
        self.assertEqual("dispatching", restarted.execution_checkpoint_phase())

        with self.assertRaisesRegex(RuntimeError, "provider idempotency state is unresolved"):
            restarted.reconcile_execution_uncertainty(actor="operator@example.com")

        # Provider ambiguity cannot unlock lifecycle traffic or replay remediation.
        self.assertEqual("execution_uncertain", restarted.checkpoint_state())
        self.assertEqual("dispatching", restarted.execution_checkpoint_phase())
        readiness = _service_readiness(restarted)
        self.assertFalse(readiness["ready"])
        self.assertEqual("execution_uncertain", readiness["checks"]["checkpoint"])
        self.assertEqual("dispatching", readiness["checks"]["remediation_execution_phase"])
        self.assertEqual(1, len([event for event in self.server.events if event[0] == "POST"]))
        self.assertEqual(1, len([event for event in self.server.events if event[0] == "GET"]))

        # A later authoritative read may resolve ambiguity, but still cannot replay.
        self.server.reconciliation_mode = "normal"
        refreshed = restarted.reconcile_execution_uncertainty(actor="operator@example.com")
        self.assertIsNone(refreshed.approval)
        self.assertEqual("synchronized", restarted.checkpoint_state())
        self.assertEqual("none", restarted.execution_checkpoint_phase())
        self.assertEqual(1, len([event for event in self.server.events if event[0] == "POST"]))
        self.assertEqual(2, len([event for event in self.server.events if event[0] == "GET"]))

        # Recovery wrote a new evidence revision; a final restart has no stale approval.
        final_restart = build_service(
            JsonCheckpointStore(self.checkpoint_path),
            self.production_client(),
            [],
        )
        self.assertEqual("synchronized", final_restart.checkpoint_state())
        self.assertIsNone(final_restart.status().approval)
        self.assertEqual(1, len([event for event in self.server.events if event[0] == "POST"]))

    def test_malformed_json_stays_execution_uncertain_until_valid_reconciliation(self):
        self.assert_fail_closed_then_recovers("malformed")

    def test_wrong_operation_echo_stays_execution_uncertain_until_valid_reconciliation(self):
        self.assert_fail_closed_then_recovers("wrong_operation_id")

    def test_unknown_provider_state_stays_execution_uncertain_until_valid_reconciliation(self):
        self.assert_fail_closed_then_recovers("unknown_state")

    def test_timeout_stays_execution_uncertain_until_valid_reconciliation(self):
        self.assert_fail_closed_then_recovers("timeout")


if __name__ == "__main__":
    unittest.main()

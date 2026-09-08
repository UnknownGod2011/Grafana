from __future__ import annotations

import json
import shutil
import ssl
import subprocess
import tempfile
import threading
import unittest
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from http_remediation_transport import HttpRemediationTransport
from production_remediation import RemediationRequest


class ProviderHandler(BaseHTTPRequestHandler):
    server_version = "StageGuardTestProvider/1"

    def log_message(self, _format, *_args):
        return

    def _json(self, status: int, document: dict) -> None:
        payload = json.dumps(document, sort_keys=True, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_POST(self) -> None:
        if self.path != "/v1/recover":
            self._json(404, {"error": "not found"})
            return
        length = int(self.headers.get("Content-Length", "0"))
        document = json.loads(self.rfile.read(length).decode("utf-8"))
        operation_id = document["operation_id"]
        self.server.events.append(("POST", self.path, operation_id, length))
        self.server.accepted.add(operation_id)
        self._json(200, {"accepted": True, "operation_id": operation_id})

    def do_GET(self) -> None:
        prefix = "/v1/operations/"
        if not self.path.startswith(prefix):
            self._json(404, {"error": "not found"})
            return
        operation_id = self.path[len(prefix):]
        self.server.events.append(("GET", self.path, operation_id, 0))
        if operation_id not in self.server.accepted:
            self._json(404, {"error": "not found"})
            return
        self._json(200, {"operation_id": operation_id, "state": "accepted"})


@unittest.skipUnless(shutil.which("openssl"), "requires openssl to create an ephemeral test certificate")
class HttpRemediationTlsIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.cert = root / "cert.pem"
        self.key = root / "key.pem"
        subprocess.run(
            [
                shutil.which("openssl"),
                "req",
                "-x509",
                "-newkey",
                "rsa:2048",
                "-nodes",
                "-keyout",
                str(self.key),
                "-out",
                str(self.cert),
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
        server_context.load_cert_chain(certfile=str(self.cert), keyfile=str(self.key))
        self.server.socket = server_context.wrap_socket(self.server.socket, server_side=True)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

        self.client_context = ssl.create_default_context()
        self.client_context.check_hostname = False
        self.client_context.verify_mode = ssl.CERT_NONE

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        self.tmp.cleanup()

    def _urlopen(self, request, *, timeout):
        return urllib.request.urlopen(request, timeout=timeout, context=self.client_context)

    def test_real_tls_execute_then_get_only_reconciliation(self) -> None:
        port = self.server.server_address[1]
        transport = HttpRemediationTransport(
            f"https://127.0.0.1:{port}/v1/recover",
            "test-only-bearer",
            f"https://127.0.0.1:{port}/v1/operations",
            urlopen=self._urlopen,
        )
        request = RemediationRequest(
            "sg-" + "a" * 40,
            "recover_uplink",
            "prod-1",
            "uplink-a",
        )

        result = transport.execute(request, timeout_seconds=2.0)
        self.assertTrue(result.accepted)
        self.assertEqual(200, result.status_code)
        self.assertEqual("accepted", transport.reconcile(request.operation_id, timeout_seconds=2.0))

        self.assertEqual(2, len(self.server.events))
        post, lookup = self.server.events
        self.assertEqual(("POST", "/v1/recover", request.operation_id), post[:3])
        self.assertGreater(post[3], 0)
        self.assertEqual("GET", lookup[0])
        self.assertEqual(request.operation_id, lookup[2])
        self.assertEqual(0, lookup[3], "reconciliation must not carry a request body")
        self.assertEqual(1, sum(1 for event in self.server.events if event[0] == "POST"))

    def test_real_tls_unknown_operation_is_not_found_without_post(self) -> None:
        port = self.server.server_address[1]
        transport = HttpRemediationTransport(
            f"https://127.0.0.1:{port}/v1/recover",
            "test-only-bearer",
            f"https://127.0.0.1:{port}/v1/operations",
            urlopen=self._urlopen,
        )
        operation_id = "sg-" + "b" * 40

        self.assertEqual("not_found", transport.reconcile(operation_id, timeout_seconds=2.0))
        self.assertEqual(1, len(self.server.events))
        self.assertEqual("GET", self.server.events[0][0])
        self.assertEqual(0, sum(1 for event in self.server.events if event[0] == "POST"))


if __name__ == "__main__":
    unittest.main()

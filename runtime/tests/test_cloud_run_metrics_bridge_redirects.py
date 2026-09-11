from __future__ import annotations

import sys
import threading
import unittest
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


RUNTIME = Path(__file__).resolve().parents[1]
if str(RUNTIME) not in sys.path:
    sys.path.insert(0, str(RUNTIME))

from cloud_run_metrics_bridge import (  # noqa: E402
    CloudRunMetricsClient,
    _open_without_redirects,
)


VALID_METRICS = b"stageguard_remediation_execution_deadline_exceeded 0\n"


class _Response:
    def __init__(self, body: bytes) -> None:
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, _size: int = -1) -> bytes:
        return self.body


class CloudRunMetricsRedirectTests(unittest.TestCase):
    def test_bearer_token_is_an_unredirected_request_header(self) -> None:
        observed = {}

        def opener(request, *, timeout):
            observed["ordinary"] = dict(request.headers)
            observed["unredirected"] = dict(request.unredirected_hdrs)
            observed["all"] = dict(request.header_items())
            observed["timeout"] = timeout
            return _Response(VALID_METRICS)

        client = CloudRunMetricsClient(
            "https://stageguard.example",
            token_supplier=lambda _audience: "credential-sentinel",
            opener=opener,
        )
        self.assertEqual(client.fetch(), VALID_METRICS)

        self.assertNotIn("Authorization", observed["ordinary"])
        self.assertEqual(observed["unredirected"]["Authorization"], "Bearer credential-sentinel")
        self.assertEqual(observed["all"]["Authorization"], "Bearer credential-sentinel")
        self.assertEqual(observed["timeout"], 10.0)

    def test_production_opener_refuses_redirect_without_contacting_destination(self) -> None:
        destination = {"calls": 0, "authorization": None}

        class DestinationHandler(BaseHTTPRequestHandler):
            def log_message(self, _format, *_args):
                return

            def do_GET(self):  # noqa: N802
                destination["calls"] += 1
                destination["authorization"] = self.headers.get("Authorization")
                body = VALID_METRICS
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        destination_server = ThreadingHTTPServer(("127.0.0.1", 0), DestinationHandler)
        destination_thread = threading.Thread(target=destination_server.serve_forever, daemon=True)
        destination_thread.start()

        destination_url = f"http://127.0.0.1:{destination_server.server_address[1]}/metrics"

        class RedirectHandler(BaseHTTPRequestHandler):
            def log_message(self, _format, *_args):
                return

            def do_GET(self):  # noqa: N802
                self.send_response(302)
                self.send_header("Location", destination_url)
                self.send_header("Content-Length", "0")
                self.end_headers()

        redirect_server = ThreadingHTTPServer(("127.0.0.1", 0), RedirectHandler)
        redirect_thread = threading.Thread(target=redirect_server.serve_forever, daemon=True)
        redirect_thread.start()

        try:
            request = urllib.request.Request(
                f"http://127.0.0.1:{redirect_server.server_address[1]}/metrics",
                method="GET",
            )
            request.add_unredirected_header("Authorization", "Bearer credential-sentinel")

            with self.assertRaises(urllib.error.HTTPError) as caught:
                _open_without_redirects(request, timeout=2.0)

            self.assertEqual(caught.exception.code, 302)
            self.assertEqual(destination["calls"], 0)
            self.assertIsNone(destination["authorization"])
        finally:
            redirect_server.shutdown()
            redirect_server.server_close()
            redirect_thread.join(timeout=2)
            destination_server.shutdown()
            destination_server.server_close()
            destination_thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import io
import sys
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path


RUNTIME = Path(__file__).resolve().parents[1]
if str(RUNTIME) not in sys.path:
    sys.path.insert(0, str(RUNTIME))

from cloud_run_metrics_bridge import (  # noqa: E402
    BridgeConfigurationError,
    CloudRunMetricsClient,
    make_server,
    normalize_audience,
    normalize_target,
)


class _Response:
    def __init__(self, body: bytes) -> None:
        self._body = io.BytesIO(body)

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, size: int = -1) -> bytes:
        return self._body.read(size)


class CloudRunMetricsBridgeTests(unittest.TestCase):
    def test_target_is_restricted_to_https_service_origin(self) -> None:
        metrics_url, audience = normalize_target("https://stageguard-abc.a.run.app")
        self.assertEqual(metrics_url, "https://stageguard-abc.a.run.app/metrics")
        self.assertEqual(audience, "https://stageguard-abc.a.run.app")
        for invalid in (
            "http://stageguard.example",
            " https://stageguard.example",
            "https://user:pass@stageguard.example",
            "https://stageguard.example/v1/incident",
            "https://stageguard.example?token=x",
            "https://stageguard.example/#fragment",
        ):
            with self.subTest(invalid=invalid):
                with self.assertRaises(BridgeConfigurationError):
                    normalize_target(invalid)

    def test_audience_is_restricted_to_https_origin(self) -> None:
        self.assertEqual(normalize_audience("https://stageguard.example/"), "https://stageguard.example")
        for invalid in ("http://stageguard.example", "https://stageguard.example/path", "https://u:p@stageguard.example"):
            with self.subTest(invalid=invalid):
                with self.assertRaises(BridgeConfigurationError):
                    normalize_audience(invalid)

    def test_timeout_must_be_finite_and_positive(self) -> None:
        for invalid in (0, -1, True, float("nan"), float("inf"), float("-inf"), "not-a-number"):
            with self.subTest(invalid=invalid):
                with self.assertRaises(BridgeConfigurationError):
                    CloudRunMetricsClient("https://stageguard.example", timeout_seconds=invalid)

    def test_fetch_adds_only_bridge_owned_authorization_header(self) -> None:
        observed = {}

        def opener(request, *, timeout):
            observed["url"] = request.full_url
            observed["headers"] = dict(request.header_items())
            observed["timeout"] = timeout
            return _Response(b"stageguard_remediation_execution_active 0\n")

        client = CloudRunMetricsClient(
            "https://stageguard.example",
            token_supplier=lambda audience: "short-lived-id-token" if audience == "https://stageguard.example" else "",
            opener=opener,
        )
        body = client.fetch()
        self.assertEqual(body, b"stageguard_remediation_execution_active 0\n")
        self.assertEqual(observed["url"], "https://stageguard.example/metrics")
        self.assertEqual(observed["headers"]["Authorization"], "Bearer short-lived-id-token")
        self.assertEqual(observed["headers"]["Accept"], "text/plain")
        self.assertEqual(observed["timeout"], 10.0)

    def test_non_loopback_bind_requires_explicit_opt_in(self) -> None:
        client = CloudRunMetricsClient(
            "https://stageguard.example",
            token_supplier=lambda _audience: "token",
            opener=lambda *_args, **_kwargs: _Response(b"ok\n"),
        )
        with self.assertRaises(BridgeConfigurationError):
            make_server(client, "0.0.0.0", 0)

    def test_http_bridge_sanitizes_upstream_failures(self) -> None:
        def failing_opener(*_args, **_kwargs):
            raise RuntimeError("secret-provider-detail token=never-leak")

        client = CloudRunMetricsClient(
            "https://stageguard.example",
            token_supplier=lambda _audience: "top-secret-token",
            opener=failing_opener,
        )
        server = make_server(client, "127.0.0.1", 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            url = f"http://127.0.0.1:{server.server_address[1]}/metrics"
            with self.assertRaises(urllib.error.HTTPError) as caught:
                urllib.request.urlopen(url, timeout=2)
            body = caught.exception.read().decode("utf-8")
            self.assertEqual(caught.exception.code, 502)
            self.assertEqual(body, "stageguard metrics upstream unavailable\n")
            self.assertNotIn("secret-provider-detail", body)
            self.assertNotIn("top-secret-token", body)
            self.assertNotIn("stageguard.example", body)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()

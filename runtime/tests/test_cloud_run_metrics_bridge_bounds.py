from __future__ import annotations

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
    MAX_BRIDGE_BEARER_TOKEN_LENGTH,
    MAX_TIMEOUT_SECONDS,
    BridgeConfigurationError,
    CloudRunMetricsClient,
    make_server,
    normalize_bridge_bearer_token,
)


class _NeverCalledClient:
    def fetch(self) -> bytes:
        raise AssertionError("authorization must fail before any upstream fetch")


class CloudRunMetricsBridgeBoundsTests(unittest.TestCase):
    def test_timeout_accepts_exact_upper_bound(self) -> None:
        client = CloudRunMetricsClient(
            "https://stageguard.example",
            timeout_seconds=MAX_TIMEOUT_SECONDS,
        )
        self.assertEqual(client.timeout_seconds, MAX_TIMEOUT_SECONDS)

    def test_timeout_rejects_values_above_upper_bound(self) -> None:
        for invalid in (MAX_TIMEOUT_SECONDS + 0.001, 600, 3600, 1e12):
            with self.subTest(invalid=invalid):
                with self.assertRaises(BridgeConfigurationError):
                    CloudRunMetricsClient(
                        "https://stageguard.example",
                        timeout_seconds=invalid,
                    )

    def test_bridge_bearer_token_accepts_exact_maximum_length(self) -> None:
        token = "a" * MAX_BRIDGE_BEARER_TOKEN_LENGTH
        self.assertEqual(normalize_bridge_bearer_token(token), token)

    def test_bridge_bearer_token_rejects_oversized_configured_secret(self) -> None:
        with self.assertRaises(BridgeConfigurationError):
            normalize_bridge_bearer_token("a" * (MAX_BRIDGE_BEARER_TOKEN_LENGTH + 1))

    def test_oversized_presented_bearer_is_rejected_before_upstream_fetch(self) -> None:
        expected = "b" * 32
        server = make_server(
            _NeverCalledClient(),
            "127.0.0.1",
            0,
            bearer_token=expected,
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            request = urllib.request.Request(
                f"http://127.0.0.1:{server.server_address[1]}/metrics",
                headers={"Authorization": "Bearer " + "a" * (MAX_BRIDGE_BEARER_TOKEN_LENGTH + 1)},
            )
            with self.assertRaises(urllib.error.HTTPError) as caught:
                urllib.request.urlopen(request, timeout=2)
            self.assertEqual(caught.exception.code, 401)
            self.assertEqual(caught.exception.read(), b"unauthorized\n")
            self.assertEqual(
                caught.exception.headers.get("WWW-Authenticate"),
                'Bearer realm="stageguard-metrics"',
            )
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import io
import sys
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest import mock


RUNTIME = Path(__file__).resolve().parents[1]
if str(RUNTIME) not in sys.path:
    sys.path.insert(0, str(RUNTIME))

import cloud_run_metrics_acceptance as acceptance  # noqa: E402
from cloud_run_metrics_bridge import (  # noqa: E402
    BridgeConfigurationError,
    CloudRunMetricsClient,
    MIN_NETWORK_BEARER_TOKEN_LENGTH,
    make_server,
    normalize_bridge_bearer_token,
)


VALID_METRICS = b"""# TYPE stageguard_remediation_execution_deadline_exceeded gauge
stageguard_remediation_execution_deadline_exceeded 0
"""
NETWORK_SECRET = "network-scrape-secret-0123456789abcdef"
LOCAL_SECRET = "local-scrape-secret"
EPHEMERAL_SECRET = "ephemeral-local-secret-0123456789abcdef"


class _Response:
    def __init__(self, body: bytes) -> None:
        self._body = io.BytesIO(body)

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, size: int = -1) -> bytes:
        return self._body.read(size)


class _FakeServer:
    def __init__(self, port: int) -> None:
        self.server_address = ("0.0.0.0", port)

    def shutdown(self) -> None:
        return None

    def server_close(self) -> None:
        return None


class _FakeThread:
    def join(self, timeout: float | None = None) -> None:
        return None


class CloudRunMetricsBridgeInboundAuthTests(unittest.TestCase):
    def _client(self, calls: list[str] | None = None) -> CloudRunMetricsClient:
        def opener(*_args, **_kwargs):
            if calls is not None:
                calls.append("upstream")
            return _Response(VALID_METRICS)

        return CloudRunMetricsClient(
            "https://stageguard.example",
            token_supplier=lambda _audience: "cloud-run-id-token",
            opener=opener,
        )

    def test_bridge_bearer_token_validation_is_fail_closed(self) -> None:
        self.assertIsNone(normalize_bridge_bearer_token(None))
        self.assertEqual(normalize_bridge_bearer_token("scrape-secret"), "scrape-secret")
        self.assertEqual(normalize_bridge_bearer_token("abc.DEF_123-~+/=="), "abc.DEF_123-~+/==")
        for invalid in (
            "",
            " scrape-secret",
            "scrape-secret ",
            "a\nb",
            "a\rb",
            "two words",
            "comma,separated",
            "unicode-雪",
        ):
            with self.subTest(invalid=invalid):
                with self.assertRaises(BridgeConfigurationError):
                    normalize_bridge_bearer_token(invalid)

    def test_non_loopback_bind_requires_opt_in_auth_and_minimum_secret_length(self) -> None:
        client = self._client()
        with self.assertRaises(BridgeConfigurationError):
            make_server(client, "0.0.0.0", 0)
        with self.assertRaises(BridgeConfigurationError):
            make_server(client, "0.0.0.0", 0, allow_network_bind=True)
        with self.assertRaises(BridgeConfigurationError):
            make_server(
                client,
                "0.0.0.0",
                0,
                allow_network_bind=True,
                bearer_token="x" * (MIN_NETWORK_BEARER_TOKEN_LENGTH - 1),
            )

        with mock.patch("cloud_run_metrics_bridge.ThreadingHTTPServer") as server_class:
            make_server(
                client,
                "0.0.0.0",
                9112,
                allow_network_bind=True,
                bearer_token=NETWORK_SECRET,
            )
        server_class.assert_called_once()
        _address, handler = server_class.call_args.args
        self.assertEqual(_address, ("0.0.0.0", 9112))
        self.assertEqual(handler.bridge_bearer_token, NETWORK_SECRET)

    def test_loopback_can_still_use_short_valid_local_secret(self) -> None:
        client = self._client()
        with mock.patch("cloud_run_metrics_bridge.ThreadingHTTPServer") as server_class:
            make_server(client, "127.0.0.1", 9112, bearer_token="dev-secret")
        server_class.assert_called_once()
        _address, handler = server_class.call_args.args
        self.assertEqual(_address, ("127.0.0.1", 9112))
        self.assertEqual(handler.bridge_bearer_token, "dev-secret")

    def test_healthz_stays_public_but_readyz_and_metrics_require_bearer(self) -> None:
        calls: list[str] = []
        server = make_server(
            self._client(calls),
            "127.0.0.1",
            0,
            bearer_token=LOCAL_SECRET,
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            base = f"http://127.0.0.1:{server.server_address[1]}"
            with urllib.request.urlopen(f"{base}/healthz", timeout=2) as response:
                self.assertEqual(response.status, 200)
                self.assertEqual(response.read(), b'{"ok":true}')

            for path in ("/readyz", "/metrics"):
                with self.subTest(path=path):
                    with self.assertRaises(urllib.error.HTTPError) as caught:
                        urllib.request.urlopen(f"{base}{path}", timeout=2)
                    self.assertEqual(caught.exception.code, 401)
                    self.assertEqual(caught.exception.headers.get("WWW-Authenticate"), 'Bearer realm="stageguard-metrics"')
                    self.assertEqual(caught.exception.read(), b"unauthorized\n")

            # Unauthorized probes must not mint a Cloud Run token or contact the
            # upstream private service.
            self.assertEqual(calls, [])

            request = urllib.request.Request(
                f"{base}/metrics",
                headers={"Authorization": f"Bearer {LOCAL_SECRET}"},
            )
            with urllib.request.urlopen(request, timeout=2) as response:
                self.assertEqual(response.status, 200)
                self.assertEqual(response.read(), VALID_METRICS)
            self.assertEqual(calls, ["upstream"])
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_wrong_bearer_does_not_contact_upstream(self) -> None:
        calls: list[str] = []
        server = make_server(
            self._client(calls),
            "127.0.0.1",
            0,
            bearer_token="correct-secret",
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            request = urllib.request.Request(
                f"http://127.0.0.1:{server.server_address[1]}/readyz",
                headers={"Authorization": "Bearer wrong-secret"},
            )
            with self.assertRaises(urllib.error.HTTPError) as caught:
                urllib.request.urlopen(request, timeout=2)
            self.assertEqual(caught.exception.code, 401)
            self.assertEqual(calls, [])
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_prometheus_config_can_authenticate_without_cloud_run_token(self) -> None:
        config = acceptance._prometheus_config(
            49123,
            acceptance.DEFAULT_JOB_NAME,
            EPHEMERAL_SECRET,
        )
        self.assertIn("host.docker.internal:49123", config)
        self.assertIn("authorization:", config)
        self.assertIn(f'credentials: "{EPHEMERAL_SECRET}"', config)
        self.assertNotIn("cloud-run-id-token", config)
        self.assertNotIn("stageguard.example", config)

    def test_acceptance_reuses_one_ephemeral_scrape_token_across_restart(self) -> None:
        client = mock.Mock()
        starts = [
            (_FakeServer(49123), _FakeThread()),
            (_FakeServer(49123), _FakeThread()),
        ]
        captured_config: list[str] = []

        def start_prometheus(config_path: Path, _image: str):
            captured_config.append(config_path.read_text(encoding="utf-8"))
            return "prometheus-container", 49090

        with mock.patch.object(acceptance, "verify_unauthorized_upstream", return_value=403):
            with mock.patch.object(acceptance, "_docker_available", return_value=None):
                with mock.patch.object(acceptance.secrets, "token_urlsafe", return_value=EPHEMERAL_SECRET):
                    with mock.patch.object(acceptance, "_start_bridge", side_effect=starts) as start_bridge:
                        with mock.patch.object(acceptance, "_stop_bridge"):
                            with mock.patch.object(acceptance, "wait_for_bridge_ready") as ready:
                                with mock.patch.object(acceptance, "_start_prometheus", side_effect=start_prometheus):
                                    with mock.patch.object(acceptance, "_stop_container"):
                                        with mock.patch.object(
                                            acceptance,
                                            "wait_for_prometheus_up",
                                            side_effect=lambda _url, _job, expected, _timeout: expected,
                                        ):
                                            result = acceptance.run_acceptance(
                                                "https://stageguard.example",
                                                client_factory=mock.Mock(return_value=client),
                                                timeout_seconds=1,
                                                prometheus_start_timeout_seconds=1,
                                                scrape_timeout_seconds=1,
                                            )

        self.assertEqual(result.recovered_up, 1.0)
        self.assertEqual(len(captured_config), 1)
        self.assertIn(f'credentials: "{EPHEMERAL_SECRET}"', captured_config[0])
        self.assertEqual(
            start_bridge.call_args_list[0].kwargs,
            {"bearer_token": EPHEMERAL_SECRET},
        )
        self.assertEqual(start_bridge.call_args_list[1].args, (client, 49123))
        self.assertEqual(
            start_bridge.call_args_list[1].kwargs,
            {"bearer_token": EPHEMERAL_SECRET},
        )
        self.assertEqual(ready.call_count, 2)
        for call in ready.call_args_list:
            self.assertEqual(call.args[2], EPHEMERAL_SECRET)
        self.assertEqual(client.fetch.call_count, 2)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import io
import sys
import unittest
from pathlib import Path


RUNTIME = Path(__file__).resolve().parents[1]
if str(RUNTIME) not in sys.path:
    sys.path.insert(0, str(RUNTIME))

from cloud_run_metrics_bridge import BridgeConfigurationError, CloudRunMetricsClient  # noqa: E402


VALID_METRICS = b"stageguard_remediation_execution_deadline_exceeded 0\n"


class _Response:
    def __init__(self, body: bytes) -> None:
        self._body = io.BytesIO(body)

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, size: int = -1) -> bytes:
        return self._body.read(size)


class CloudRunMetricsAudienceBoundaryTests(unittest.TestCase):
    def test_default_audience_is_target_origin(self) -> None:
        observed = {}

        def token_supplier(audience: str) -> str:
            observed["audience"] = audience
            return "short-lived-id-token"

        def opener(request, *, timeout):
            observed["url"] = request.full_url
            observed["authorization"] = dict(request.header_items())["Authorization"]
            return _Response(VALID_METRICS)

        client = CloudRunMetricsClient(
            "https://stageguard.example",
            token_supplier=token_supplier,
            opener=opener,
        )

        self.assertEqual(client.fetch(), VALID_METRICS)
        self.assertEqual(observed["audience"], "https://stageguard.example")
        self.assertEqual(observed["url"], "https://stageguard.example/metrics")
        self.assertEqual(observed["authorization"], "Bearer short-lived-id-token")

    def test_explicit_same_origin_audience_is_allowed_without_opt_in(self) -> None:
        client = CloudRunMetricsClient(
            "https://stageguard.example/",
            audience="https://stageguard.example",
            token_supplier=lambda _audience: "token",
            opener=lambda *_args, **_kwargs: _Response(VALID_METRICS),
        )
        self.assertEqual(client.fetch(), VALID_METRICS)

    def test_cross_origin_audience_is_rejected_by_default(self) -> None:
        token_calls = []

        def token_supplier(audience: str) -> str:
            token_calls.append(audience)
            return "must-not-be-minted"

        with self.assertRaises(BridgeConfigurationError):
            CloudRunMetricsClient(
                "https://metrics-target.example",
                audience="https://different-audience.example",
                token_supplier=token_supplier,
            )

        self.assertEqual(token_calls, [])

    def test_cross_origin_audience_requires_explicit_opt_in(self) -> None:
        observed = {}

        def token_supplier(audience: str) -> str:
            observed["audience"] = audience
            return "audience-scoped-token"

        def opener(request, *, timeout):
            observed["url"] = request.full_url
            observed["authorization"] = dict(request.header_items())["Authorization"]
            return _Response(VALID_METRICS)

        client = CloudRunMetricsClient(
            "https://custom-domain.example",
            audience="https://stageguard-abc.a.run.app",
            allow_cross_origin_audience=True,
            token_supplier=token_supplier,
            opener=opener,
        )

        self.assertEqual(client.fetch(), VALID_METRICS)
        self.assertEqual(observed["audience"], "https://stageguard-abc.a.run.app")
        self.assertEqual(observed["url"], "https://custom-domain.example/metrics")
        self.assertEqual(observed["authorization"], "Bearer audience-scoped-token")

    def test_opt_in_flag_must_be_boolean(self) -> None:
        for invalid in (1, 0, "true", None):
            with self.subTest(invalid=invalid):
                with self.assertRaises(BridgeConfigurationError):
                    CloudRunMetricsClient(
                        "https://stageguard.example",
                        allow_cross_origin_audience=invalid,  # type: ignore[arg-type]
                    )


if __name__ == "__main__":
    unittest.main()

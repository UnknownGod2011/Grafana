from __future__ import annotations

import io
import json
import unittest
import urllib.error
from unittest.mock import patch

from http_remediation_transport import HttpRemediationTransport
from production_remediation import RemediationRequest


class FakeResponse:
    def __init__(self, status: int, body: bytes) -> None:
        self.status = status
        self._body = io.BytesIO(body)

    def read(self, size: int = -1) -> bytes:
        return self._body.read(size)

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        return None


class HttpRemediationTransportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.request = RemediationRequest("sg-" + "a" * 40, "recover_uplink", "prod-1", "uplink-a")

    def test_requires_https_and_process_owned_credential(self) -> None:
        with self.assertRaisesRegex(ValueError, "HTTPS"):
            HttpRemediationTransport("http://writer.internal/recover", "secret")
        with self.assertRaisesRegex(ValueError, "credential"):
            HttpRemediationTransport("https://writer.example/recover", "")
        with self.assertRaisesRegex(ValueError, "query or fragment"):
            HttpRemediationTransport("https://writer.example/recover?target=x", "secret")
        with self.assertRaisesRegex(ValueError, "reconciliation endpoint must use HTTPS"):
            HttpRemediationTransport(
                "https://writer.example/recover", "secret", "http://writer.example/operations"
            )

    def test_sends_server_idempotency_key_and_strict_body(self) -> None:
        body = json.dumps({"accepted": True, "operation_id": self.request.operation_id}).encode()
        captured = {}

        def fake_urlopen(req, timeout):
            captured["request"] = req
            captured["timeout"] = timeout
            return FakeResponse(200, body)

        transport = HttpRemediationTransport("https://writer.example/v1/recover", "top-secret")
        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            result = transport.execute(self.request, timeout_seconds=2.5)

        sent = captured["request"]
        self.assertTrue(result.accepted)
        self.assertEqual(captured["timeout"], 2.5)
        self.assertEqual(sent.get_header("Idempotency-key"), self.request.operation_id)
        self.assertEqual(sent.get_header("Authorization"), "Bearer top-secret")
        self.assertEqual(json.loads(sent.data), {
            "operation_id": self.request.operation_id,
            "action": "recover_uplink",
            "production_id": "prod-1",
            "target": "uplink-a",
        })

    def test_rejects_wrong_operation_echo_and_extra_response_fields(self) -> None:
        transport = HttpRemediationTransport("https://writer.example/v1/recover", "secret")
        for document in (
            {"accepted": True, "operation_id": "sg-" + "b" * 40},
            {"accepted": True, "operation_id": self.request.operation_id, "detail": "ignored"},
        ):
            with self.subTest(document=document), patch(
                "urllib.request.urlopen",
                return_value=FakeResponse(200, json.dumps(document).encode()),
            ):
                result = transport.execute(self.request, timeout_seconds=1.0)
                self.assertFalse(result.accepted)
                self.assertFalse(result.retryable)

    def test_retryability_is_bounded_to_transient_statuses(self) -> None:
        transport = HttpRemediationTransport("https://writer.example/v1/recover", "secret")
        for status, retryable in ((429, True), (503, True), (409, False), (400, False)):
            error = urllib.error.HTTPError(transport.endpoint, status, "failure", {}, None)
            with self.subTest(status=status), patch("urllib.request.urlopen", side_effect=error):
                result = transport.execute(self.request, timeout_seconds=1.0)
                self.assertFalse(result.accepted)
                self.assertEqual(result.status_code, status)
                self.assertEqual(result.retryable, retryable)

    def test_network_failure_does_not_expose_endpoint_or_secret(self) -> None:
        transport = HttpRemediationTransport("https://writer.example/v1/recover", "very-secret")
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("very-secret at writer.example")):
            result = transport.execute(self.request, timeout_seconds=1.0)
        self.assertFalse(result.accepted)
        self.assertIsNone(result.status_code)
        self.assertTrue(result.retryable)
        self.assertNotIn("secret", repr(result))
        self.assertNotIn("writer.example", repr(result))

    def test_oversized_or_malformed_success_response_fails_closed(self) -> None:
        transport = HttpRemediationTransport("https://writer.example/v1/recover", "secret")
        with patch("urllib.request.urlopen", return_value=FakeResponse(200, b"x" * (16 * 1024 + 1))):
            with self.assertRaisesRegex(ValueError, "size limit"):
                transport.execute(self.request, timeout_seconds=1.0)
        with patch("urllib.request.urlopen", return_value=FakeResponse(200, b"not-json")):
            result = transport.execute(self.request, timeout_seconds=1.0)
            self.assertFalse(result.accepted)

    def test_reconcile_is_read_only_and_uses_only_server_owned_operation_id(self) -> None:
        operation_id = self.request.operation_id
        body = json.dumps({"operation_id": operation_id, "state": "accepted"}).encode()
        captured = {}

        def fake_urlopen(req, timeout):
            captured["request"] = req
            captured["timeout"] = timeout
            return FakeResponse(200, body)

        transport = HttpRemediationTransport(
            "https://writer.example/v1/recover",
            "top-secret",
            "https://writer.example/v1/operations",
        )
        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            state = transport.reconcile(operation_id, timeout_seconds=1.25)

        request = captured["request"]
        self.assertEqual("accepted", state)
        self.assertEqual("GET", request.get_method())
        self.assertIsNone(request.data)
        self.assertEqual(1.25, captured["timeout"])
        self.assertEqual(
            f"https://writer.example/v1/operations/{operation_id}", request.full_url
        )
        self.assertEqual("Bearer top-secret", request.get_header("Authorization"))
        self.assertNotIn("recover_uplink", request.full_url)
        self.assertNotIn("prod-1", request.full_url)
        self.assertNotIn("uplink-a", request.full_url)

    def test_reconcile_maps_404_to_not_found_without_retry_or_replay(self) -> None:
        transport = HttpRemediationTransport(
            "https://writer.example/v1/recover",
            "secret",
            "https://writer.example/v1/operations",
        )
        error = urllib.error.HTTPError(
            "https://writer.example/v1/operations/x", 404, "missing", {}, None
        )
        with patch("urllib.request.urlopen", side_effect=error) as urlopen:
            state = transport.reconcile(self.request.operation_id, timeout_seconds=1.0)
        self.assertEqual("not_found", state)
        self.assertEqual(1, urlopen.call_count)
        self.assertEqual("GET", urlopen.call_args.args[0].get_method())

    def test_reconcile_failures_and_malformed_documents_are_unknown(self) -> None:
        transport = HttpRemediationTransport(
            "https://writer.example/v1/recover",
            "secret",
            "https://writer.example/v1/operations",
        )
        cases = (
            TimeoutError("timeout"),
            urllib.error.URLError("secret at writer.example"),
            FakeResponse(200, b"not-json"),
            FakeResponse(200, json.dumps({"operation_id": self.request.operation_id, "state": "pending"}).encode()),
            FakeResponse(200, json.dumps({"operation_id": "sg-" + "b" * 40, "state": "accepted"}).encode()),
            FakeResponse(200, json.dumps({"operation_id": self.request.operation_id, "state": "accepted", "detail": "x"}).encode()),
            FakeResponse(200, b"x" * (16 * 1024 + 1)),
        )
        for result in cases:
            with self.subTest(result=type(result).__name__), patch(
                "urllib.request.urlopen",
                side_effect=result if isinstance(result, BaseException) else None,
                return_value=None if isinstance(result, BaseException) else result,
            ):
                state = transport.reconcile(self.request.operation_id, timeout_seconds=1.0)
                self.assertEqual("unknown", state)

    def test_reconcile_without_endpoint_or_with_invalid_operation_id_fails_closed(self) -> None:
        transport = HttpRemediationTransport("https://writer.example/v1/recover", "secret")
        with patch("urllib.request.urlopen") as urlopen:
            self.assertEqual("unknown", transport.reconcile(self.request.operation_id, timeout_seconds=1.0))
            self.assertEqual("unknown", transport.reconcile("attacker-controlled", timeout_seconds=1.0))
        urlopen.assert_not_called()


if __name__ == "__main__":
    unittest.main()

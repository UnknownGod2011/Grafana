from __future__ import annotations

import io
import json
import unittest
import urllib.error
import urllib.request

from http_remediation_transport import HttpRemediationTransport, _RejectRedirects
from production_remediation import RemediationRequest


class FakeResponse:
    def __init__(self, status: int, body: bytes, *, final_url: str | None = None) -> None:
        self.status = status
        self._body = io.BytesIO(body)
        self._final_url = final_url

    def read(self, size: int = -1) -> bytes:
        return self._body.read(size)

    def geturl(self) -> str:
        if self._final_url is None:
            raise AttributeError("no final URL in this test response")
        return self._final_url

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        return None


class LegacyFakeResponse:
    """Response without geturl(), matching existing injected transport seams."""

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

    def _transport(self, opener, *, reconcile: bool = False) -> HttpRemediationTransport:
        return HttpRemediationTransport(
            "https://writer.example/v1/recover",
            "top-secret",
            "https://writer.example/v1/operations" if reconcile else None,
            urlopen=opener,
        )

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
            return LegacyFakeResponse(200, body)

        result = self._transport(fake_urlopen).execute(self.request, timeout_seconds=2.5)

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

    def test_sensitive_headers_are_not_copied_to_redirect_request(self) -> None:
        captured = {}

        def fake_urlopen(req, timeout):
            captured["request"] = req
            return LegacyFakeResponse(
                200,
                json.dumps({"accepted": True, "operation_id": self.request.operation_id}).encode(),
            )

        self._transport(fake_urlopen).execute(self.request, timeout_seconds=1.0)
        original = captured["request"]
        redirected = urllib.request.HTTPRedirectHandler().redirect_request(
            original,
            None,
            302,
            "moved",
            {},
            "https://attacker.example/capture",
        )
        self.assertIsNotNone(redirected)
        self.assertIsNone(redirected.get_header("Authorization"))
        self.assertIsNone(redirected.get_header("Idempotency-key"))
        self.assertIsNone(redirected.data)

    def test_production_redirect_handler_refuses_redirects(self) -> None:
        request = urllib.request.Request("https://writer.example/v1/recover", method="GET")
        with self.assertRaises(urllib.error.HTTPError) as raised:
            _RejectRedirects().redirect_request(
                request,
                None,
                302,
                "moved",
                {},
                "https://attacker.example/capture",
            )
        self.assertEqual(302, raised.exception.code)

    def test_custom_opener_redirected_execute_response_fails_closed(self) -> None:
        body = json.dumps({"accepted": True, "operation_id": self.request.operation_id}).encode()
        transport = self._transport(
            lambda _req, timeout: FakeResponse(
                200,
                body,
                final_url="https://attacker.example/capture",
            )
        )
        result = transport.execute(self.request, timeout_seconds=1.0)
        self.assertFalse(result.accepted)
        self.assertFalse(result.retryable)

    def test_custom_opener_redirected_reconciliation_is_unknown(self) -> None:
        body = json.dumps({"operation_id": self.request.operation_id, "state": "accepted"}).encode()
        transport = self._transport(
            lambda _req, timeout: FakeResponse(
                200,
                body,
                final_url="https://attacker.example/capture",
            ),
            reconcile=True,
        )
        self.assertEqual("unknown", transport.reconcile(self.request.operation_id, timeout_seconds=1.0))

    def test_rejects_wrong_operation_echo_and_extra_response_fields(self) -> None:
        for document in (
            {"accepted": True, "operation_id": "sg-" + "b" * 40},
            {"accepted": True, "operation_id": self.request.operation_id, "detail": "ignored"},
        ):
            with self.subTest(document=document):
                transport = self._transport(
                    lambda _req, timeout, doc=document: LegacyFakeResponse(200, json.dumps(doc).encode())
                )
                result = transport.execute(self.request, timeout_seconds=1.0)
                self.assertFalse(result.accepted)
                self.assertFalse(result.retryable)

    def test_retryability_is_bounded_to_transient_statuses(self) -> None:
        for status, retryable in ((429, True), (503, True), (409, False), (400, False)):
            def fail(req, timeout, code=status):
                raise urllib.error.HTTPError(req.full_url, code, "failure", {}, None)

            with self.subTest(status=status):
                result = self._transport(fail).execute(self.request, timeout_seconds=1.0)
                self.assertFalse(result.accepted)
                self.assertEqual(result.status_code, status)
                self.assertEqual(result.retryable, retryable)

    def test_network_failure_does_not_expose_endpoint_or_secret(self) -> None:
        def fail(_req, timeout):
            raise urllib.error.URLError("very-secret at writer.example")

        result = self._transport(fail).execute(self.request, timeout_seconds=1.0)
        self.assertFalse(result.accepted)
        self.assertIsNone(result.status_code)
        self.assertTrue(result.retryable)
        self.assertNotIn("secret", repr(result))
        self.assertNotIn("writer.example", repr(result))

    def test_oversized_or_malformed_success_response_fails_closed(self) -> None:
        oversized = self._transport(
            lambda _req, timeout: LegacyFakeResponse(200, b"x" * (16 * 1024 + 1))
        )
        with self.assertRaisesRegex(ValueError, "size limit"):
            oversized.execute(self.request, timeout_seconds=1.0)

        malformed = self._transport(lambda _req, timeout: LegacyFakeResponse(200, b"not-json"))
        result = malformed.execute(self.request, timeout_seconds=1.0)
        self.assertFalse(result.accepted)

    def test_reconcile_is_read_only_and_uses_only_server_owned_operation_id(self) -> None:
        operation_id = self.request.operation_id
        body = json.dumps({"operation_id": operation_id, "state": "accepted"}).encode()
        captured = {}

        def fake_urlopen(req, timeout):
            captured["request"] = req
            captured["timeout"] = timeout
            return LegacyFakeResponse(200, body)

        state = self._transport(fake_urlopen, reconcile=True).reconcile(operation_id, timeout_seconds=1.25)

        request = captured["request"]
        self.assertEqual("accepted", state)
        self.assertEqual("GET", request.get_method())
        self.assertIsNone(request.data)
        self.assertEqual(1.25, captured["timeout"])
        self.assertEqual(f"https://writer.example/v1/operations/{operation_id}", request.full_url)
        self.assertEqual("Bearer top-secret", request.get_header("Authorization"))
        self.assertNotIn("recover_uplink", request.full_url)
        self.assertNotIn("prod-1", request.full_url)
        self.assertNotIn("uplink-a", request.full_url)

    def test_reconcile_accepts_only_contract_bound_404_as_not_found(self) -> None:
        calls = []

        def missing(req, timeout):
            calls.append(req)
            body = json.dumps({"operation_id": self.request.operation_id, "state": "not_found"}).encode()
            raise urllib.error.HTTPError(req.full_url, 404, "missing", {}, io.BytesIO(body))

        state = self._transport(missing, reconcile=True).reconcile(
            self.request.operation_id,
            timeout_seconds=1.0,
        )
        self.assertEqual("not_found", state)
        self.assertEqual(1, len(calls))
        self.assertEqual("GET", calls[0].get_method())

    def test_generic_or_malformed_404_reconciliation_is_unknown(self) -> None:
        operation_id = self.request.operation_id
        cases = (
            b"",
            b"not-json",
            json.dumps({"error": "not_found"}).encode(),
            json.dumps({"operation_id": "sg-" + "b" * 40, "state": "not_found"}).encode(),
            json.dumps({"operation_id": operation_id, "state": "accepted"}).encode(),
            json.dumps({"operation_id": operation_id, "state": "not_found", "detail": "proxy"}).encode(),
            b"x" * (16 * 1024 + 1),
        )
        for body in cases:
            def missing(req, timeout, payload=body):
                raise urllib.error.HTTPError(req.full_url, 404, "missing", {}, io.BytesIO(payload))

            with self.subTest(body=body[:32]):
                state = self._transport(missing, reconcile=True).reconcile(operation_id, timeout_seconds=1.0)
                self.assertEqual("unknown", state)

    def test_reconcile_404_from_different_final_url_is_unknown(self) -> None:
        body = json.dumps({"operation_id": self.request.operation_id, "state": "not_found"}).encode()

        def missing(_req, timeout):
            raise urllib.error.HTTPError(
                "https://proxy.example/not-found",
                404,
                "missing",
                {},
                io.BytesIO(body),
            )

        state = self._transport(missing, reconcile=True).reconcile(
            self.request.operation_id,
            timeout_seconds=1.0,
        )
        self.assertEqual("unknown", state)

    def test_reconcile_failures_and_malformed_documents_are_unknown(self) -> None:
        cases = (
            TimeoutError("timeout"),
            urllib.error.URLError("secret at writer.example"),
            LegacyFakeResponse(200, b"not-json"),
            LegacyFakeResponse(200, json.dumps({"operation_id": self.request.operation_id, "state": "pending"}).encode()),
            LegacyFakeResponse(200, json.dumps({"operation_id": "sg-" + "b" * 40, "state": "accepted"}).encode()),
            LegacyFakeResponse(200, json.dumps({"operation_id": self.request.operation_id, "state": "accepted", "detail": "x"}).encode()),
            LegacyFakeResponse(200, b"x" * (16 * 1024 + 1)),
        )
        for outcome in cases:
            def opener(_req, timeout, result=outcome):
                if isinstance(result, BaseException):
                    raise result
                return result

            with self.subTest(result=type(outcome).__name__):
                state = self._transport(opener, reconcile=True).reconcile(
                    self.request.operation_id,
                    timeout_seconds=1.0,
                )
                self.assertEqual("unknown", state)

    def test_reconcile_without_endpoint_or_with_invalid_operation_id_fails_closed(self) -> None:
        calls = []

        def opener(req, timeout):
            calls.append(req)
            return LegacyFakeResponse(200, b"{}")

        transport = self._transport(opener)
        self.assertEqual("unknown", transport.reconcile(self.request.operation_id, timeout_seconds=1.0))
        self.assertEqual("unknown", transport.reconcile("attacker-controlled", timeout_seconds=1.0))
        self.assertEqual([], calls)


if __name__ == "__main__":
    unittest.main()

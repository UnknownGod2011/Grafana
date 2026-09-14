from __future__ import annotations

import http.client
import json
import socket
import threading
import unittest

from remediation_receiver import ReferenceRemediationServer


class RemediationReceiverTests(unittest.TestCase):
    def setUp(self) -> None:
        self.server = ReferenceRemediationServer(("127.0.0.1", 0), "secret")
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.port = self.server.server_address[1]

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def _post(self, document: dict, *, token: str = "secret", key: str | None = None):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=2)
        body = json.dumps(document)
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Idempotency-Key": key or document.get("operation_id", ""),
        }
        connection.request("POST", "/v1/recover", body=body, headers=headers)
        response = connection.getresponse()
        payload = json.loads(response.read().decode())
        connection.close()
        return response.status, payload

    def _get_operation(self, operation_id: str, *, token: str = "secret"):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=2)
        connection.request(
            "GET",
            f"/v1/operations/{operation_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        response = connection.getresponse()
        payload = json.loads(response.read().decode())
        connection.close()
        return response.status, payload

    def _raw_status(self, request: bytes) -> int:
        with socket.create_connection(("127.0.0.1", self.port), timeout=2) as sock:
            sock.sendall(request)
            response = sock.recv(4096)
        status_line = response.split(b"\r\n", 1)[0]
        return int(status_line.split(b" ", 2)[1])

    @staticmethod
    def _document(operation_id: str) -> dict:
        return {
            "operation_id": operation_id,
            "action": "recover_uplink",
            "production_id": "prod-1",
            "target": "uplink-a",
        }

    def _raw_post(self, extra_headers: list[tuple[str, str]], *, body: bytes | None = None) -> int:
        operation_id = "sg-" + "a" * 40
        if body is None:
            body = json.dumps(self._document(operation_id), separators=(",", ":")).encode()
        headers = [
            ("Host", f"127.0.0.1:{self.port}"),
            ("Authorization", "Bearer secret"),
            ("Content-Type", "application/json"),
            ("Idempotency-Key", operation_id),
        ] + extra_headers
        wire = [b"POST /v1/recover HTTP/1.1\r\n"]
        wire.extend(f"{name}: {value}\r\n".encode() for name, value in headers)
        wire.append(b"\r\n")
        wire.append(body)
        return self._raw_status(b"".join(wire))

    def test_repeated_identical_operation_is_idempotently_accepted(self) -> None:
        operation_id = "sg-" + "a" * 40
        document = self._document(operation_id)
        first = self._post(document)
        second = self._post(document)
        self.assertEqual(first, (200, {"accepted": True, "operation_id": operation_id}))
        self.assertEqual(second, first)
        self.assertEqual(len(self.server.operations), 1)

    def test_operation_id_cannot_be_reused_for_different_mutation(self) -> None:
        operation_id = "sg-" + "a" * 40
        first = self._document(operation_id)
        second = dict(first, target="uplink-b")
        self.assertEqual(self._post(first)[0], 200)
        status, payload = self._post(second)
        self.assertEqual(status, 409)
        self.assertEqual(payload["error"], "operation_identity_reused_with_different_request")

    def test_authentication_and_idempotency_header_are_required(self) -> None:
        operation_id = "sg-" + "a" * 40
        document = self._document(operation_id)
        self.assertEqual(self._post(document, token="wrong")[0], 401)
        self.assertEqual(self._post(document, key="sg-" + "b" * 40)[0], 409)
        self.assertEqual(len(self.server.operations), 0)

    def test_duplicate_authorization_header_fails_closed_before_mutation(self) -> None:
        body = json.dumps(self._document("sg-" + "a" * 40), separators=(",", ":")).encode()
        status = self._raw_post(
            [("Authorization", "Bearer secret"), ("Content-Length", str(len(body)))],
            body=body,
        )
        self.assertEqual(401, status)
        self.assertEqual({}, self.server.operations)

    def test_duplicate_idempotency_header_fails_closed_before_mutation(self) -> None:
        body = json.dumps(self._document("sg-" + "a" * 40), separators=(",", ":")).encode()
        status = self._raw_post(
            [("Idempotency-Key", "sg-" + "a" * 40), ("Content-Length", str(len(body)))],
            body=body,
        )
        self.assertEqual(400, status)
        self.assertEqual({}, self.server.operations)

    def test_ambiguous_request_framing_fails_closed_before_mutation(self) -> None:
        body = json.dumps(self._document("sg-" + "a" * 40), separators=(",", ":")).encode()
        cases = (
            [("Content-Length", str(len(body))), ("Content-Length", str(len(body)))],
            [("Transfer-Encoding", "chunked")],
            [("Content-Length", str(len(body))), ("Transfer-Encoding", "chunked")],
        )
        for extra_headers in cases:
            with self.subTest(extra_headers=extra_headers):
                self.assertEqual(400, self._raw_post(extra_headers, body=body))
                self.assertEqual({}, self.server.operations)

    def test_non_json_media_type_is_rejected_before_mutation(self) -> None:
        body = json.dumps(self._document("sg-" + "a" * 40), separators=(",", ":")).encode()
        status = self._raw_post(
            [("Content-Type", "text/plain"), ("Content-Length", str(len(body)))],
            body=body,
        )
        self.assertEqual(415, status)
        self.assertEqual({}, self.server.operations)

    def test_reconciliation_reports_not_found_then_accepted_without_replay(self) -> None:
        operation_id = "sg-" + "a" * 40

        missing_status, missing = self._get_operation(operation_id)
        self.assertEqual(404, missing_status)
        self.assertEqual({"operation_id": operation_id, "state": "not_found"}, missing)
        self.assertEqual({}, self.server.operations)

        self.assertEqual(200, self._post(self._document(operation_id))[0])
        accepted_status, accepted = self._get_operation(operation_id)
        self.assertEqual(200, accepted_status)
        self.assertEqual({"operation_id": operation_id, "state": "accepted"}, accepted)
        self.assertEqual(1, len(self.server.operations))

    def test_reconciliation_requires_authentication_and_never_echoes_mutation_detail(self) -> None:
        operation_id = "sg-" + "a" * 40
        self.assertEqual(200, self._post(self._document(operation_id))[0])

        status, payload = self._get_operation(operation_id, token="wrong")
        self.assertEqual(401, status)
        self.assertEqual({"error": "unauthorized"}, payload)

        status, payload = self._get_operation(operation_id)
        self.assertEqual(200, status)
        self.assertEqual({"operation_id", "state"}, set(payload))
        serialized = json.dumps(payload)
        self.assertNotIn("recover_uplink", serialized)
        self.assertNotIn("prod-1", serialized)
        self.assertNotIn("uplink-a", serialized)

    def test_invalid_reconciliation_operation_id_fails_closed(self) -> None:
        status, payload = self._get_operation("attacker-controlled")
        self.assertEqual(400, status)
        self.assertEqual({"error": "invalid_operation_id"}, payload)


if __name__ == "__main__":
    unittest.main()

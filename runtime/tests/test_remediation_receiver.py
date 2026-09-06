from __future__ import annotations

import http.client
import json
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

    def test_repeated_identical_operation_is_idempotently_accepted(self) -> None:
        operation_id = "sg-" + "a" * 40
        document = {
            "operation_id": operation_id,
            "action": "recover_uplink",
            "production_id": "prod-1",
            "target": "uplink-a",
        }
        first = self._post(document)
        second = self._post(document)
        self.assertEqual(first, (200, {"accepted": True, "operation_id": operation_id}))
        self.assertEqual(second, first)
        self.assertEqual(len(self.server.operations), 1)

    def test_operation_id_cannot_be_reused_for_different_mutation(self) -> None:
        operation_id = "sg-" + "a" * 40
        first = {
            "operation_id": operation_id,
            "action": "recover_uplink",
            "production_id": "prod-1",
            "target": "uplink-a",
        }
        second = dict(first, target="uplink-b")
        self.assertEqual(self._post(first)[0], 200)
        status, payload = self._post(second)
        self.assertEqual(status, 409)
        self.assertEqual(payload["error"], "operation_identity_reused_with_different_request")

    def test_authentication_and_idempotency_header_are_required(self) -> None:
        operation_id = "sg-" + "a" * 40
        document = {
            "operation_id": operation_id,
            "action": "recover_uplink",
            "production_id": "prod-1",
            "target": "uplink-a",
        }
        self.assertEqual(self._post(document, token="wrong")[0], 401)
        self.assertEqual(self._post(document, key="sg-" + "b" * 40)[0], 409)
        self.assertEqual(len(self.server.operations), 0)


if __name__ == "__main__":
    unittest.main()

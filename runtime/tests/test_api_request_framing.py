import json
import socket
import threading
import unittest

from api import make_server
from identity import StaticBearerIdentityProvider
from incident_service import IncidentService, MemoryAuditLog
from remediation import ActionResult


class SequenceMetrics:
    def __init__(self, values):
        self.values = list(values)
        self.index = 0

    def instant(self, _query):
        value = self.values[self.index]
        self.index += 1
        return value


class FakeRemediation:
    def recover_uplink(self, _production_id, _uplink):
        return ActionResult(True, "ok")


def diagnosed_metrics():
    return SequenceMetrics([4.0, 18.0, 41.0, 37.0, 0.2, 0.1])


class ApiRequestFramingTests(unittest.TestCase):
    def setUp(self):
        self.audit = MemoryAuditLog()
        self.service = IncidentService(
            diagnosed_metrics(),
            FakeRemediation(),
            self.audit,
            clock_ms=lambda: 1,
            id_factory=lambda: "incident-framing-001",
            recovery_sleep=lambda _: None,
        )
        provider = StaticBearerIdentityProvider({"operator-secret": "operator@example.com"})
        self.server = make_server(self.service, "127.0.0.1", 0, identity_provider=provider)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.port = self.server.server_address[1]

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def raw_post(self, extra_headers, body=b"{}"):
        request_lines = [
            "POST /v1/investigate HTTP/1.1",
            f"Host: 127.0.0.1:{self.port}",
            "Authorization: Bearer operator-secret",
            "Connection: close",
            *extra_headers,
            "",
            "",
        ]
        request = "\r\n".join(request_lines).encode("ascii") + body
        with socket.create_connection(("127.0.0.1", self.port), timeout=2) as sock:
            sock.settimeout(2)
            sock.sendall(request)
            chunks = []
            while True:
                chunk = sock.recv(65536)
                if not chunk:
                    break
                chunks.append(chunk)
        response = b"".join(chunks)
        head, payload = response.split(b"\r\n\r\n", 1)
        status_line = head.split(b"\r\n", 1)[0].decode("ascii")
        status = int(status_line.split(" ", 2)[1])
        return status, json.loads(payload.decode("utf-8"))

    def assert_framing_rejected(self, headers, body=b"{}", detail=None):
        status, payload = self.raw_post(headers, body)
        self.assertEqual(400, status)
        self.assertEqual("invalid_request", payload["error"])
        if detail is not None:
            self.assertEqual(detail, payload["detail"])
        self.assertEqual([], self.audit.events, "ambiguous framing must not reach lifecycle mutation")
        self.assertIsNone(self.service.status())

    def test_duplicate_conflicting_content_length_is_rejected_before_body_read(self):
        self.assert_framing_rejected(
            [
                "Content-Type: application/json",
                "Content-Length: 2",
                "Content-Length: 3",
            ],
            detail="Content-Length must be supplied at most once",
        )

    def test_duplicate_identical_content_length_is_also_rejected(self):
        self.assert_framing_rejected(
            [
                "Content-Type: application/json",
                "Content-Length: 2",
                "Content-Length: 2",
            ],
            detail="Content-Length must be supplied at most once",
        )

    def test_transfer_encoding_is_rejected_even_without_content_length(self):
        self.assert_framing_rejected(
            [
                "Content-Type: application/json",
                "Transfer-Encoding: chunked",
            ],
            body=b"2\r\n{}\r\n0\r\n\r\n",
            detail="Transfer-Encoding is not supported",
        )

    def test_transfer_encoding_and_content_length_is_rejected(self):
        self.assert_framing_rejected(
            [
                "Content-Type: application/json",
                "Content-Length: 2",
                "Transfer-Encoding: chunked",
            ],
            detail="Transfer-Encoding is not supported",
        )

    def test_single_content_length_still_allows_normal_json_request(self):
        status, payload = self.raw_post(
            [
                "Content-Type: application/json",
                "Content-Length: 2",
            ]
        )
        self.assertEqual(200, status)
        self.assertEqual("diagnosed", payload["incident"]["report"]["status"])
        self.assertEqual("operator@example.com", self.audit.events[0].actor)


if __name__ == "__main__":
    unittest.main()

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


class ApiProtocolPreflightTests(unittest.TestCase):
    def setUp(self):
        self.audit = MemoryAuditLog()
        self.service = IncidentService(
            diagnosed_metrics(),
            FakeRemediation(),
            self.audit,
            clock_ms=lambda: 1,
            id_factory=lambda: "incident-protocol-001",
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

    def raw_request(self, request: bytes):
        with socket.create_connection(("127.0.0.1", self.port), timeout=2) as sock:
            sock.settimeout(0.75)
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

    def headers_only_post(self, path, extra_headers=()):
        request_lines = [
            f"POST {path} HTTP/1.1",
            f"Host: 127.0.0.1:{self.port}",
            "Connection: close",
            "Content-Type: application/json",
            "Content-Length: 4096",
            *extra_headers,
            "",
            "",
        ]
        return self.raw_request("\r\n".join(request_lines).encode("ascii"))

    def assert_no_mutation(self):
        self.assertEqual([], self.audit.events)
        self.assertIsNone(self.service.status())

    def test_unknown_post_path_is_rejected_without_waiting_for_declared_body(self):
        status, payload = self.headers_only_post("/v1/not-a-route")
        self.assertEqual(404, status)
        self.assertEqual("not_found", payload["error"])
        self.assert_no_mutation()

    def test_query_bearing_mutation_route_is_rejected_before_body_read(self):
        status, payload = self.headers_only_post("/v1/investigate?unexpected=1")
        self.assertEqual(404, status)
        self.assertEqual("not_found", payload["error"])
        self.assert_no_mutation()

    def test_expect_header_is_rejected_before_authentication_or_body_read(self):
        status, payload = self.headers_only_post("/v1/investigate", ("Expect: 100-continue",))
        self.assertEqual(417, status)
        self.assertEqual("expectation_failed", payload["error"])
        self.assertEqual("Expect is not supported", payload["detail"])
        self.assert_no_mutation()

    def test_handle_expect_100_remains_fail_closed_if_server_moves_to_http11(self):
        self.server.RequestHandlerClass.protocol_version = "HTTP/1.1"
        status, payload = self.headers_only_post("/v1/investigate", ("Expect: 100-continue",))
        self.assertEqual(417, status)
        self.assertEqual("expectation_failed", payload["error"])
        self.assert_no_mutation()

    def test_normal_authenticated_post_still_succeeds(self):
        request = (
            f"POST /v1/investigate HTTP/1.1\r\n"
            f"Host: 127.0.0.1:{self.port}\r\n"
            "Authorization: Bearer operator-secret\r\n"
            "Connection: close\r\n"
            "Content-Type: application/json\r\n"
            "Content-Length: 2\r\n\r\n{}"
        ).encode("ascii")
        status, payload = self.raw_request(request)
        self.assertEqual(200, status)
        self.assertEqual("diagnosed", payload["incident"]["report"]["status"])
        self.assertEqual("operator@example.com", self.audit.events[0].actor)


if __name__ == "__main__":
    unittest.main()

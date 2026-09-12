import http.client
import json
import threading
import unittest

from api import make_server
from identity import AuthenticationError
from incident_service import IncidentService, MemoryAuditLog
from remediation import ActionResult


_SECRET = "provider-secret=SENSITIVE_SENTINEL verifier=https://private.example/token"


class SequenceMetrics:
    def __init__(self):
        self.values = [4.0, 18.0, 41.0, 37.0, 0.2, 0.1]
        self.index = 0

    def instant(self, _query):
        value = self.values[self.index]
        self.index += 1
        return value


class FakeRemediation:
    def recover_uplink(self, _production_id, _uplink):
        return ActionResult(True, "ok")


class SecretBearingIdentityProvider:
    is_development_only = False

    def authenticate(self, _handler):
        raise AuthenticationError(_SECRET)


class AuthenticationErrorRedactionApiTests(unittest.TestCase):
    def setUp(self):
        self.service = IncidentService(
            SequenceMetrics(),
            FakeRemediation(),
            MemoryAuditLog(),
            clock_ms=lambda: 1,
            id_factory=lambda: "incident-auth-redaction",
            recovery_sleep=lambda _: None,
        )
        self.server = make_server(
            self.service,
            "127.0.0.1",
            0,
            identity_provider=SecretBearingIdentityProvider(),
        )
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.port = self.server.server_address[1]

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def request(self, method, path, payload=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=2)
        headers = {}
        body = None
        if payload is not None:
            body = json.dumps(payload)
            headers["Content-Type"] = "application/json"
        connection.request(method, path, body=body, headers=headers)
        response = connection.getresponse()
        raw = response.read().decode("utf-8")
        response_headers = dict(response.getheaders())
        connection.close()
        return response.status, json.loads(raw), response_headers, raw

    def assert_redacted_unauthorized(self, status, body, headers, raw):
        self.assertEqual(401, status)
        self.assertEqual("unauthorized", body["error"])
        self.assertEqual("authentication required", body["detail"])
        self.assertIn("WWW-Authenticate", headers)
        self.assertNotIn("SENSITIVE_SENTINEL", raw)
        self.assertNotIn("private.example", raw)
        self.assertNotIn("provider-secret", raw)

    def test_console_authentication_failure_redacts_provider_detail(self):
        status, body, headers, raw = self.request("GET", "/console")
        self.assert_redacted_unauthorized(status, body, headers, raw)

    def test_authenticated_get_redacts_provider_detail(self):
        status, body, headers, raw = self.request("GET", "/v1/incident")
        self.assert_redacted_unauthorized(status, body, headers, raw)

    def test_authenticated_post_redacts_provider_detail(self):
        status, body, headers, raw = self.request("POST", "/v1/investigate", {})
        self.assert_redacted_unauthorized(status, body, headers, raw)

    def test_stageguard_owned_authentication_messages_remain_actionable(self):
        self.assertEqual("invalid bearer credential", str(AuthenticationError("invalid bearer credential")))
        self.assertEqual("invalid IAP assertion", str(AuthenticationError("invalid IAP assertion")))


if __name__ == "__main__":
    unittest.main()

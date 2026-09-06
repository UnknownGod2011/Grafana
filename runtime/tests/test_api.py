import http.client
import json
import threading
import unittest
from unittest.mock import patch

from api import make_server
from identity import LocalDevelopmentIdentityProvider, StaticBearerIdentityProvider
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


class IncidentApiTests(unittest.TestCase):
    def setUp(self):
        self.audit = MemoryAuditLog()
        self.service = IncidentService(
            diagnosed_metrics(),
            FakeRemediation(),
            self.audit,
            clock_ms=lambda: 1,
            id_factory=lambda: "incident-001",
            recovery_sleep=lambda _: None,
        )
        self.provider = StaticBearerIdentityProvider({"operator-secret": "operator@example.com"})
        self.server = make_server(self.service, "127.0.0.1", 0, identity_provider=self.provider)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.port = self.server.server_address[1]

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def request(self, method, path, payload=None, token=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=2)
        headers = {}
        body = None
        if token is not None:
            headers["Authorization"] = f"Bearer {token}"
        if payload is not None:
            body = json.dumps(payload)
            headers["Content-Type"] = "application/json"
        connection.request(method, path, body=body, headers=headers)
        response = connection.getresponse()
        data = json.loads(response.read().decode("utf-8"))
        response_headers = dict(response.getheaders())
        connection.close()
        return response.status, data, response_headers

    def test_mutating_endpoint_requires_authentication(self):
        status, body, headers = self.request("POST", "/v1/investigate", {})
        self.assertEqual(401, status)
        self.assertEqual("unauthorized", body["error"])
        self.assertIn("WWW-Authenticate", headers)
        self.assertEqual([], self.audit.events)

    def test_investigation_actor_comes_from_identity_provider(self):
        status, body, _ = self.request("POST", "/v1/investigate", {}, "operator-secret")
        self.assertEqual(200, status)
        self.assertEqual("diagnosed", body["incident"]["report"]["status"])
        self.assertEqual("operator@example.com", self.audit.events[0].actor)

    def test_approval_rejects_body_supplied_identity_and_uses_authenticated_subject(self):
        status, body, _ = self.request("POST", "/v1/investigate", {}, "operator-secret")
        self.assertEqual(200, status)
        incident = body["incident"]

        status, body, _ = self.request(
            "POST",
            "/v1/approve",
            {
                "incident_id": incident["incident_id"],
                "revision": incident["revision"],
                "approved_by": "attacker@example.com",
            },
            "operator-secret",
        )
        self.assertEqual(400, status)
        self.assertIn("unsupported fields", body["detail"])

        status, body, _ = self.request(
            "POST",
            "/v1/approve",
            {"incident_id": incident["incident_id"], "revision": incident["revision"]},
            "operator-secret",
        )
        self.assertEqual(200, status)
        self.assertEqual("operator@example.com", body["incident"]["approval"]["approved_by"])
        self.assertEqual("operator@example.com", self.audit.events[-1].actor)

    def test_health_endpoint_stays_unauthenticated(self):
        status, body, _ = self.request("GET", "/healthz")
        self.assertEqual(200, status)
        self.assertTrue(body["ok"])

    def test_non_loopback_refuses_development_identity_before_binding(self):
        with patch("api.ThreadingHTTPServer") as server_factory:
            with self.assertRaises(ValueError):
                make_server(
                    self.service,
                    "0.0.0.0",
                    9110,
                    identity_provider=LocalDevelopmentIdentityProvider("local"),
                )
            server_factory.assert_not_called()

    def test_non_loopback_allows_explicit_non_development_provider(self):
        with patch("api.ThreadingHTTPServer") as server_factory:
            make_server(self.service, "0.0.0.0", 9110, identity_provider=self.provider)
            server_factory.assert_called_once()


if __name__ == "__main__":
    unittest.main()

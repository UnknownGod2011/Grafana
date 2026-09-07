import http.client
import json
import threading
import unittest
from unittest.mock import patch

from api import make_server
from identity import StaticBearerIdentityProvider
from incident_service import IncidentService, MemoryAuditLog
from remediation import ActionResult


class Metrics:
    def instant(self, _query):
        return 0.0


class Remediation:
    def recover_uplink(self, _production_id, _uplink):
        return ActionResult(False, "disabled")


class ReadinessApiTests(unittest.TestCase):
    def setUp(self):
        service = IncidentService(Metrics(), Remediation(), MemoryAuditLog())
        provider = StaticBearerIdentityProvider({"unused": "operator"})
        self.server = make_server(service, "127.0.0.1", 0, identity_provider=provider)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.port = self.server.server_address[1]

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def get_raw(self, path):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=2)
        connection.request("GET", path)
        response = connection.getresponse()
        body = response.read().decode("utf-8")
        status = response.status
        content_type = response.getheader("Content-Type")
        connection.close()
        return status, content_type, body

    def get(self, path):
        status, _content_type, body = self.get_raw(path)
        return status, json.loads(body)

    def test_healthz_remains_cheap_and_independent_of_readiness(self):
        with patch("api._service_readiness", side_effect=RuntimeError("must not run")):
            status, payload = self.get("/healthz")
        self.assertEqual(200, status)
        self.assertEqual({"ok": True}, payload)

    def test_readyz_returns_200_only_when_all_bounded_checks_are_ready(self):
        value = {
            "ready": True,
            "checks": {
                "metric_activation": "ok",
                "loki_activation": "ok",
                "prometheus_mcp": "ok",
                "loki_mcp": "ok",
            },
        }
        with patch("api._service_readiness", return_value=value):
            status, payload = self.get("/readyz")
        self.assertEqual(200, status)
        self.assertEqual(value, payload)

    def test_readyz_accepts_bounded_stale_external_state(self):
        value = {
            "ready": True,
            "checks": {
                "metric_activation": "ok",
                "loki_activation": "ok",
                "prometheus_mcp": "stale",
                "loki_mcp": "ok",
            },
        }
        with patch("api._service_readiness", return_value=value):
            status, payload = self.get("/readyz")
        self.assertEqual(200, status)
        self.assertEqual("stale", payload["checks"]["prometheus_mcp"])

    def test_readyz_returns_503_without_authentication_and_without_error_detail(self):
        value = {
            "ready": False,
            "checks": {
                "metric_activation": "ok",
                "loki_activation": "failed",
                "prometheus_mcp": "ok",
                "loki_mcp": "failed",
            },
        }
        with patch("api._service_readiness", return_value=value):
            status, payload = self.get("/readyz")
        self.assertEqual(503, status)
        self.assertEqual(value, payload)
        self.assertNotIn("detail", payload)

    def test_unexpected_probe_failure_is_redacted_and_fails_closed(self):
        with patch("api._service_readiness", side_effect=RuntimeError("token=secret https://private")):
            status, payload = self.get("/readyz")
        self.assertEqual(503, status)
        self.assertFalse(payload["ready"])
        self.assertNotIn("secret", str(payload))
        self.assertNotIn("private", str(payload))

    def test_metrics_surface_is_prometheus_text_and_never_requires_operator_auth(self):
        text = "stageguard_readiness_ready 1\n"
        with patch("api._service_metrics", return_value=text):
            status, content_type, body = self.get_raw("/metrics")
        self.assertEqual(200, status)
        self.assertTrue(content_type.startswith("text/plain"))
        self.assertEqual(text, body)

    def test_metrics_failure_is_redacted(self):
        with patch("api._service_metrics", side_effect=RuntimeError("token=secret https://private")):
            status, _content_type, body = self.get_raw("/metrics")
        self.assertEqual(200, status)
        self.assertIn("metrics unavailable", body)
        self.assertNotIn("secret", body)
        self.assertNotIn("private", body)


if __name__ == "__main__":
    unittest.main()

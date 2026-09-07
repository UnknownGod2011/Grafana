import http.client
import threading
import unittest

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


class OperatorConsoleTests(unittest.TestCase):
    def setUp(self):
        service = IncidentService(Metrics(), Remediation(), MemoryAuditLog())
        provider = StaticBearerIdentityProvider({"console-token": "operator-1"})
        self.server = make_server(service, "127.0.0.1", 0, identity_provider=provider)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.port = self.server.server_address[1]

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def get(self, path, *, authenticated=False):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=2)
        headers = {"Authorization": "Bearer console-token"} if authenticated else {}
        connection.request("GET", path, headers=headers)
        response = connection.getresponse()
        body = response.read().decode("utf-8")
        result = (
            response.status,
            response.getheader("Content-Type"),
            response.getheader("Content-Security-Policy"),
            response.getheader("Cache-Control"),
            body,
        )
        connection.close()
        return result

    def test_console_requires_operator_authentication(self):
        status, content_type, _csp, cache_control, body = self.get("/console")
        self.assertEqual(401, status)
        self.assertTrue(content_type.startswith("application/json"))
        self.assertEqual("no-store", cache_control)
        self.assertNotIn("<html", body.lower())

    def test_console_is_same_origin_and_csp_locked(self):
        status, content_type, csp, cache_control, body = self.get("/console", authenticated=True)
        self.assertEqual(200, status)
        self.assertTrue(content_type.startswith("text/html"))
        self.assertEqual("no-store", cache_control)
        self.assertIn("default-src 'none'", csp)
        self.assertIn("script-src 'self'", csp)
        self.assertIn("connect-src 'self'", csp)
        self.assertIn("frame-ancestors 'none'", csp)
        self.assertIn('src="/assets/operator.js"', body)
        self.assertNotIn("http://", body)
        self.assertNotIn("https://", body)

    def test_console_assets_are_authenticated_and_have_no_embedded_credentials(self):
        for path, expected_type in (
            ("/assets/operator.js", "text/javascript"),
            ("/assets/operator.css", "text/css"),
        ):
            with self.subTest(path=path):
                status, _content_type, _csp, _cache, _body = self.get(path)
                self.assertEqual(401, status)
                status, content_type, csp, _cache, body = self.get(path, authenticated=True)
                self.assertEqual(200, status)
                self.assertTrue(content_type.startswith(expected_type))
                self.assertIn("default-src 'none'", csp)
                self.assertNotIn("GRAFANA_", body)
                self.assertNotIn("GOOGLE_API_KEY", body)
                self.assertNotIn("Authorization: Bearer", body)

    def test_console_javascript_binds_briefing_and_approval_to_current_revision(self):
        _status, _type, _csp, _cache, body = self.get("/assets/operator.js", authenticated=True)
        self.assertIn("incident_id:current.incident_id,revision:current.revision", body)
        self.assertIn("event.target.value !== current.revision", body)
        self.assertIn("data.revision!==current.revision", body)
        self.assertIn("window.confirm", body)
        self.assertNotIn("localStorage", body)
        self.assertNotIn("sessionStorage", body)

    def test_console_has_fail_closed_checkpoint_recovery_workflow(self):
        _status, _type, _csp, _cache, html = self.get("/console", authenticated=True)
        _status, _type, _csp, _cache, js = self.get("/assets/operator.js", authenticated=True)
        self.assertIn('id="lifecycle-recovery"', html)
        self.assertIn('id="reload-checkpoint"', html)
        self.assertIn('id="reconcile-execution"', html)
        self.assertIn("checkpointState === 'conflicted'", js)
        self.assertIn("checkpointState === 'execution_uncertain'", js)
        self.assertIn("q('investigate').disabled = blocked", js)
        self.assertIn("q('approval-revision').disabled = blocked", js)
        self.assertIn("lifecycleBlocked() || !approval", js)
        self.assertIn("/v1/checkpoint/reload", js)
        self.assertIn("/v1/execution/reconcile", js)
        self.assertIn("This will not replay remediation", js)

    def test_console_never_exposes_or_accepts_remediation_operation_id(self):
        _status, _type, _csp, _cache, html = self.get("/console", authenticated=True)
        _status, _type, _csp, _cache, js = self.get("/assets/operator.js", authenticated=True)
        self.assertNotIn("operation_id", html)
        self.assertNotIn("operation_id", js)
        self.assertNotIn("operation identifier", html.lower())
        # The server-owned recovery endpoints receive empty objects only.
        self.assertIn("/v1/checkpoint/reload',{method:'POST',body:{}}", js)
        self.assertIn("/v1/execution/reconcile',{method:'POST',body:{}}", js)

    def test_mutation_failures_refresh_authoritative_checkpoint_state(self):
        _status, _type, _csp, _cache, js = self.get("/assets/operator.js", authenticated=True)
        # A CAS conflict can be raised after the browser initiated execution.
        # Every lifecycle mutation catch therefore refreshes authoritative state
        # rather than leaving stale action controls enabled in the tab.
        self.assertGreaterEqual(js.count("catch(err) { message(err.message); await refresh(); }"), 6)

    def test_health_and_metrics_remain_independent_of_operator_authentication(self):
        status, _type, _csp, _cache, _body = self.get("/healthz")
        self.assertEqual(200, status)
        status, content_type, _csp, _cache, _body = self.get("/metrics")
        self.assertEqual(200, status)
        self.assertTrue(content_type.startswith("text/plain"))


if __name__ == "__main__":
    unittest.main()

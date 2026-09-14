import http.client
import json
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
        if self.index >= len(self.values):
            raise AssertionError("unexpected metric query")
        value = self.values[self.index]
        self.index += 1
        return value


class CountingRemediation:
    def __init__(self):
        self.calls = 0

    def recover_uplink(self, _production_id, _uplink):
        self.calls += 1
        return ActionResult(True, "ok")


class RecoveryRecheckApiTests(unittest.TestCase):
    def setUp(self):
        values = [
            4.0, 18.0, 41.0, 37.0, 0.2, 0.1,  # investigation
            *([8.0, 5.0] * 6),                 # execution: recovery not yet proven
            0.2, 0.2, 0.1, 0.1,               # recheck: recovery proven
        ]
        self.remediation = CountingRemediation()
        self.audit = MemoryAuditLog()
        self.service = IncidentService(
            SequenceMetrics(values),
            self.remediation,
            self.audit,
            clock_ms=lambda: 1,
            id_factory=lambda: "incident-recheck-api-001",
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

    def request(self, path, payload=None, token="operator-secret"):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=2)
        headers = {"Authorization": f"Bearer {token}"}
        body = None
        if payload is not None:
            headers["Content-Type"] = "application/json"
            body = json.dumps(payload)
        connection.request("POST", path, body=body, headers=headers)
        response = connection.getresponse()
        data = json.loads(response.read().decode("utf-8"))
        status = response.status
        connection.close()
        return status, data

    def test_authenticated_recheck_uses_fresh_evidence_without_provider_replay(self):
        status, body = self.request("/v1/investigate", {})
        self.assertEqual(200, status)
        incident = body["incident"]
        self.assertEqual("none", body["recovery"]["state"])
        self.assertFalse(body["recovery"]["recheck_eligible"])

        status, _ = self.request(
            "/v1/approve",
            {"incident_id": incident["incident_id"], "revision": incident["revision"]},
        )
        self.assertEqual(200, status)

        status, body = self.request("/v1/execute", {})
        self.assertEqual(200, status)
        self.assertEqual("recovery_unverified", body["incident"]["outcome"]["status"])
        self.assertEqual("recovery_unverified", body["recovery"]["state"])
        self.assertTrue(body["recovery"]["action_accepted"])
        self.assertTrue(body["recovery"]["recheck_eligible"])
        self.assertFalse(body["recovery"]["verified"])
        self.assertTrue(body["recovery"]["checkpoint_phase_consistent"])
        self.assertEqual(6, body["recovery"]["sample_count"])
        self.assertEqual(1, self.remediation.calls)

        status, body = self.request("/v1/recovery/recheck", {})
        self.assertEqual(200, status)
        self.assertEqual("recovered", body["incident"]["outcome"]["status"])
        self.assertEqual("recovered", body["recovery"]["state"])
        self.assertTrue(body["recovery"]["action_accepted"])
        self.assertFalse(body["recovery"]["recheck_eligible"])
        self.assertTrue(body["recovery"]["verified"])
        self.assertTrue(body["recovery"]["checkpoint_phase_consistent"])
        self.assertEqual(2, body["recovery"]["sample_count"])
        self.assertEqual(1, self.remediation.calls)
        self.assertEqual("operator@example.com", self.audit.events[-1].actor)
        self.assertEqual("recovery_rechecked", self.audit.events[-1].event_type)
        self.assertIs(False, self.audit.events[-1].payload["provider_replayed"])

    def test_recheck_rejects_body_fields_and_does_not_call_provider(self):
        before = self.remediation.calls
        status, body = self.request("/v1/recovery/recheck", {"force": True})
        self.assertEqual(400, status)
        self.assertIn("unsupported fields", body["detail"])
        self.assertEqual(before, self.remediation.calls)

    def test_recheck_requires_authentication(self):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=2)
        connection.request(
            "POST",
            "/v1/recovery/recheck",
            body="{}",
            headers={"Content-Type": "application/json"},
        )
        response = connection.getresponse()
        data = json.loads(response.read().decode("utf-8"))
        connection.close()
        self.assertEqual(401, response.status)
        self.assertEqual("unauthorized", data["error"])
        self.assertEqual(0, self.remediation.calls)


if __name__ == "__main__":
    unittest.main()

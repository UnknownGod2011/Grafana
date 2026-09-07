import http.client
import json
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


class AuditTimelineTests(unittest.TestCase):
    def make_service(self):
        return IncidentService(
            Metrics(),
            Remediation(),
            MemoryAuditLog(),
            clock_ms=lambda: 1700000000000,
            id_factory=lambda: "incident-1",
        )

    def test_timeline_is_incident_scoped_bounded_and_redacted(self):
        service = self.make_service()
        snapshot = service.investigate(actor="operator@example.com")
        service._record(
            snapshot.incident_id,
            "remediation_approved",
            "operator@example.com",
            {
                "revision": snapshot.revision,
                "action": "recover_uplink",
                "target": "secret-target",
                "endpoint": "https://private.invalid/action",
                "token": "do-not-return",
            },
        )

        first = service.audit_timeline(incident_id=snapshot.incident_id, limit=1)
        self.assertEqual(1, len(first["events"]))
        self.assertTrue(first["has_more"])
        self.assertEqual(1, first["next_after_sequence"])
        event = first["events"][0]
        self.assertEqual("investigation_completed", event["event_type"])
        self.assertEqual(12, len(event["actor_ref"]))
        self.assertNotEqual("operator@example.com", event["actor_ref"])
        self.assertNotIn("activation_profile_sha256", event["payload"])

        second = service.audit_timeline(
            incident_id=snapshot.incident_id,
            after_sequence=first["next_after_sequence"],
            limit=10,
        )
        self.assertFalse(second["has_more"])
        self.assertEqual(1, len(second["events"]))
        payload = second["events"][0]["payload"]
        self.assertEqual("recover_uplink", payload["action"])
        self.assertNotIn("target", payload)
        self.assertNotIn("endpoint", payload)
        self.assertNotIn("token", payload)

    def test_timeline_rejects_wrong_incident_and_invalid_bounds(self):
        service = self.make_service()
        service.investigate()
        with self.assertRaises(ValueError):
            service.audit_timeline(incident_id="other")
        for limit in (0, 101):
            with self.subTest(limit=limit):
                with self.assertRaises(ValueError):
                    service.audit_timeline(incident_id="incident-1", limit=limit)
        with self.assertRaises(ValueError):
            service.audit_timeline(incident_id="incident-1", after_sequence=-1)


class AuditTimelineApiTests(unittest.TestCase):
    def setUp(self):
        self.service = IncidentService(
            Metrics(), Remediation(), MemoryAuditLog(), id_factory=lambda: "incident-1"
        )
        self.service.investigate(actor="seed-actor")
        provider = StaticBearerIdentityProvider({"console-token": "operator-1"})
        self.server = make_server(self.service, "127.0.0.1", 0, identity_provider=provider)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.port = self.server.server_address[1]

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def get(self, path, authenticated=False):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=2)
        headers = {"Authorization": "Bearer console-token"} if authenticated else {}
        connection.request("GET", path, headers=headers)
        response = connection.getresponse()
        body = response.read().decode("utf-8")
        connection.close()
        return response.status, json.loads(body)

    def test_audit_endpoint_requires_identity_and_paginates(self):
        status, _body = self.get("/v1/audit?incident_id=incident-1")
        self.assertEqual(401, status)

        status, body = self.get(
            "/v1/audit?incident_id=incident-1&after_sequence=0&limit=1",
            authenticated=True,
        )
        self.assertEqual(200, status)
        timeline = body["timeline"]
        self.assertEqual("incident-1", timeline["incident_id"])
        self.assertEqual(1, len(timeline["events"]))
        self.assertEqual(1, timeline["next_after_sequence"])

    def test_audit_endpoint_rejects_unbounded_or_ambiguous_queries(self):
        for path in (
            "/v1/audit?incident_id=incident-1&limit=101",
            "/v1/audit?incident_id=incident-1&after_sequence=-1",
            "/v1/audit?incident_id=incident-1&unexpected=x",
            "/v1/audit?incident_id=incident-1&incident_id=incident-2",
        ):
            with self.subTest(path=path):
                status, body = self.get(path, authenticated=True)
                self.assertEqual(400, status)
                self.assertEqual("invalid_request", body["error"])


if __name__ == "__main__":
    unittest.main()

import http.client
import json
import threading
import unittest

from api import make_server
from evidence_errors import EvidenceUnavailable
from gemini_commander import GeminiCommander
from identity import StaticBearerIdentityProvider
from incident_service import IncidentService, MemoryAuditLog
from remediation import ActionResult


class FailingMetrics:
    """Return the symptom sample, then fail the required causal evidence read."""

    def __init__(self) -> None:
        self.calls = 0

    def instant(self, _query):
        self.calls += 1
        if self.calls == 1:
            return 4.0
        raise EvidenceUnavailable("provider-detail=SENSITIVE_SENTINEL upstream=PRIVATE_ENDPOINT_SENTINEL")


class NoopRemediation:
    def __init__(self) -> None:
        self.calls = []

    def recover_uplink(self, production_id, uplink):
        self.calls.append((production_id, uplink))
        return ActionResult(True, "accepted")


class ShouldNotRunModel:
    def __init__(self) -> None:
        self.calls = 0

    def generate(self, _context):
        self.calls += 1
        raise AssertionError("Gemini model must not run while evidence is unavailable")


class EvidenceUnavailableBriefingApiTests(unittest.TestCase):
    def setUp(self):
        self.model = ShouldNotRunModel()
        self.audit = MemoryAuditLog()
        self.remediation = NoopRemediation()
        self.service = IncidentService(
            FailingMetrics(),
            self.remediation,
            self.audit,
            commander=GeminiCommander(self.model),
            clock_ms=lambda: 123456789,
            id_factory=lambda: "incident-evidence-unavailable",
            recovery_sleep=lambda _: None,
        )
        provider = StaticBearerIdentityProvider({"test-operator-token": "operator@example.com"})
        self.server = make_server(self.service, "127.0.0.1", 0, identity_provider=provider)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.port = self.server.server_address[1]

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def request(self, method, path, payload=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=2)
        headers = {"Authorization": "Bearer test-operator-token"}
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

    def test_authenticated_briefing_request_fails_closed_before_model_invocation(self):
        status, body, _headers, raw = self.request("POST", "/v1/investigate", {})
        self.assertEqual(200, status)
        incident = body["incident"]
        self.assertEqual("abstain", incident["report"]["status"])
        self.assertEqual(["causal"], incident["report"]["unavailable_evidence"])
        self.assertNotIn("SENSITIVE_SENTINEL", raw)
        self.assertNotIn("PRIVATE_ENDPOINT_SENTINEL", raw)
        self.assertNotIn("provider-detail", raw)

        before = list(self.audit.events)
        status, body, headers, raw = self.request(
            "POST",
            "/v1/briefing",
            {"incident_id": incident["incident_id"], "revision": incident["revision"]},
        )

        self.assertEqual(400, status)
        self.assertEqual("invalid_request", body["error"])
        self.assertEqual("briefing disabled while required incident evidence is unavailable", body["detail"])
        self.assertEqual("no-store", headers.get("Cache-Control"))
        self.assertNotIn("SENSITIVE_SENTINEL", raw)
        self.assertNotIn("PRIVATE_ENDPOINT_SENTINEL", raw)
        self.assertNotIn("provider-detail", raw)

        self.assertEqual(0, self.model.calls)
        self.assertEqual(before, self.audit.events)
        self.assertEqual(["investigation_completed"], [event.event_type for event in self.audit.events])
        self.assertEqual([], self.remediation.calls)


if __name__ == "__main__":
    unittest.main()

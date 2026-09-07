import http.client
import json
import threading
import unittest

from api import make_server
from gemini_commander import GeminiCommander
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


class FakeRemediation:
    def __init__(self):
        self.calls = []

    def recover_uplink(self, production_id, uplink):
        self.calls.append((production_id, uplink))
        return ActionResult(True, "ok")


class FixedModel:
    def __init__(self):
        self.calls = []

    def generate(self, context):
        self.calls.append(dict(context))
        return {
            "headline": "Uplink packet loss isolated",
            "operator_summary": "Metric and log evidence support the deterministic uplink diagnosis.",
            "evidence_notes": ["Encoder resources are not contradictory."],
            "next_step": context["deterministic_next_step"],
            "caution": "Human approval is still required before remediation.",
        }


class FailingModel:
    def generate(self, _context):
        raise RuntimeError("provider unavailable with secret details")


def diagnosed_values(repetitions=1):
    row = [4.0, 18.0, 41.0, 37.0, 0.2, 0.1]
    return row * repetitions


class BriefingRuntimeTests(unittest.TestCase):
    def make_service(self, model=None, repetitions=1):
        audit = MemoryAuditLog()
        action = FakeRemediation()
        commander = None if model is None else GeminiCommander(model)
        service = IncidentService(
            SequenceMetrics(diagnosed_values(repetitions)),
            action,
            audit,
            commander=commander,
            clock_ms=lambda: 7,
            id_factory=lambda: "incident-001",
            recovery_sleep=lambda _: None,
        )
        return service, action, audit

    def test_briefing_is_bound_to_current_revision_and_does_not_mutate_snapshot(self):
        model = FixedModel()
        service, action, audit = self.make_service(model)
        snapshot = service.investigate(actor="operator@example.com")
        before = service.status()

        briefing = service.briefing(
            incident_id=snapshot.incident_id,
            revision=snapshot.revision,
            actor="operator@example.com",
        )

        self.assertEqual("seek_human_approval", briefing.next_step)
        self.assertEqual(before, service.status())
        self.assertIsNone(service.status().approval)
        self.assertIsNone(service.status().outcome)
        self.assertEqual([], action.calls)
        self.assertEqual(1, len(model.calls))
        self.assertEqual("briefing_generated", audit.events[-1].event_type)
        self.assertEqual(snapshot.revision, audit.events[-1].payload["revision"])
        self.assertIn("briefing_sha256", audit.events[-1].payload)
        self.assertNotIn("operator_summary", audit.events[-1].payload)

    def test_stale_revision_is_rejected_before_model_call(self):
        model = FixedModel()
        service, _, audit = self.make_service(model, repetitions=2)
        first = service.investigate()
        service.investigate()
        with self.assertRaises(ValueError):
            service.briefing(
                incident_id=first.incident_id,
                revision="stale-revision",
                actor="operator@example.com",
            )
        self.assertEqual([], model.calls)
        self.assertEqual("investigation_completed", audit.events[-1].event_type)

    def test_model_failure_is_redacted_and_state_remains_unchanged(self):
        service, action, audit = self.make_service(FailingModel())
        snapshot = service.investigate()
        before = service.status()
        with self.assertRaisesRegex(RuntimeError, "Gemini briefing generation failed"):
            service.briefing(
                incident_id=snapshot.incident_id,
                revision=snapshot.revision,
                actor="operator@example.com",
            )
        self.assertEqual(before, service.status())
        self.assertEqual([], action.calls)
        failure = audit.events[-1]
        self.assertEqual("briefing_failed", failure.event_type)
        self.assertEqual({"revision": snapshot.revision, "error_type": "RuntimeError"}, failure.payload)

    def test_disabled_commander_does_not_affect_incident_runtime(self):
        service, _, audit = self.make_service(None)
        snapshot = service.investigate()
        with self.assertRaisesRegex(RuntimeError, "Gemini briefing is not configured"):
            service.briefing(incident_id=snapshot.incident_id, revision=snapshot.revision)
        self.assertEqual(1, len(audit.events))

    def test_authenticated_api_exposes_only_revision_bound_briefing(self):
        model = FixedModel()
        service, action, audit = self.make_service(model)
        provider = StaticBearerIdentityProvider({"operator-secret": "operator@example.com"})
        server = make_server(service, "127.0.0.1", 0, identity_provider=provider)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        port = server.server_address[1]
        try:
            def request(path, payload, token="operator-secret"):
                connection = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
                headers = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
                connection.request("POST", path, body=json.dumps(payload), headers=headers)
                response = connection.getresponse()
                body = json.loads(response.read().decode("utf-8"))
                connection.close()
                return response.status, body

            status, body = request("/v1/investigate", {})
            self.assertEqual(200, status)
            incident = body["incident"]

            status, body = request(
                "/v1/briefing",
                {"incident_id": incident["incident_id"], "revision": incident["revision"]},
            )
            self.assertEqual(200, status)
            self.assertEqual(incident["revision"], body["revision"])
            self.assertEqual("seek_human_approval", body["briefing"]["next_step"])
            self.assertEqual([], action.calls)
            self.assertEqual("operator@example.com", audit.events[-1].actor)

            status, body = request(
                "/v1/briefing",
                {"incident_id": incident["incident_id"], "revision": "stale"},
            )
            self.assertEqual(400, status)
            self.assertEqual("invalid_request", body["error"])
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()

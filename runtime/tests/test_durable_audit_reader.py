import unittest
from types import SimpleNamespace

from durable_audit_reader import GoogleCloudAuditReader
from incident_service import AuditEvent, IncidentService, MemoryAuditLog
from remediation import ActionResult


NOW_MS = 1_700_000_000_000


class FakeLogger:
    full_name = "projects/test-project/logs/stageguard-audit"

    def __init__(self, payloads):
        self.payloads = list(payloads)
        self.calls = []

    def list_entries(self, **kwargs):
        self.calls.append(kwargs)
        max_results = kwargs.get("max_results")
        payloads = self.payloads if max_results is None else self.payloads[:max_results]
        return [SimpleNamespace(payload=payload) for payload in payloads]


class Metrics:
    def instant(self, _query):
        return 0.0


class Remediation:
    def recover_uplink(self, _production_id, _uplink):
        return ActionResult(False, "disabled")


def document(sequence, *, incident_id="incident-1", event_type="investigation_completed", actor="operator@example.com"):
    return {
        "schema": "stageguard.audit.v1",
        "sequence": sequence,
        "timestamp_unix_ms": NOW_MS - 1_000 + sequence,
        "incident_id": incident_id,
        "event_type": event_type,
        "actor": actor,
        "payload": {
            "revision": "rev-1",
            "status": "diagnosed",
            "confidence": 0.9,
            "evidence_mode": "metric+loki",
        },
    }


class DurableAuditReaderTests(unittest.TestCase):
    def test_reader_builds_exact_bounded_filter_and_orders_by_sequence(self):
        logger = FakeLogger([document(2), document(1)])
        reader = GoogleCloudAuditReader(logger, lookback_seconds=3600, clock_ms=lambda: NOW_MS)

        events = reader.read(incident_id="incident-1", after_sequence=0, limit=3)

        self.assertEqual([1, 2], [event.sequence for event in events])
        self.assertEqual(1, len(logger.calls))
        call = logger.calls[0]
        self.assertIn('logName="projects/test-project/logs/stageguard-audit"', call["filter_"])
        self.assertIn('jsonPayload.schema="stageguard.audit.v1"', call["filter_"])
        self.assertIn('jsonPayload.incident_id="incident-1"', call["filter_"])
        self.assertIn("jsonPayload.sequence>0", call["filter_"])
        self.assertIn('timestamp>="', call["filter_"])
        self.assertEqual("ASCENDING", call["order_by"])
        self.assertEqual(3, call["max_results"])
        self.assertEqual(3, call["page_size"])

    def test_candidate_reader_preserves_competing_sequences_for_authenticated_lineage_selection(self):
        first = document(1, actor="winner@example.com")
        competitor = document(1, actor="loser@example.com")
        second = document(2, actor="winner@example.com")
        tail = document(3, actor="uncommitted@example.com")
        logger = FakeLogger([second, competitor, tail, first])
        reader = GoogleCloudAuditReader(logger, lookback_seconds=3600, clock_ms=lambda: NOW_MS)

        candidates = reader.read_candidates(
            incident_id="incident-1", through_sequence=2, limit=10
        )

        self.assertEqual([1, 1, 2], [event.sequence for event in candidates])
        self.assertEqual({"winner@example.com", "loser@example.com"}, {event.actor for event in candidates if event.sequence == 1})
        call = logger.calls[0]
        self.assertIn("jsonPayload.sequence>0", call["filter_"])
        self.assertIn("jsonPayload.sequence<=2", call["filter_"])
        self.assertEqual("ASCENDING", call["order_by"])
        self.assertEqual(11, call["max_results"])
        self.assertEqual(100, call["page_size"])

    def test_candidate_reader_fails_closed_instead_of_silently_truncating(self):
        logger = FakeLogger([document(1), document(1, actor="two@example.com"), document(1, actor="three@example.com")])
        reader = GoogleCloudAuditReader(logger, clock_ms=lambda: NOW_MS)
        with self.assertRaisesRegex(ValueError, "safe result bound"):
            reader.read_candidates(incident_id="incident-1", through_sequence=1, limit=2)

    def test_reader_rejects_wrong_incident_unknown_shape_and_unsafe_bounds(self):
        wrong = document(1, incident_id="other")
        reader = GoogleCloudAuditReader(FakeLogger([wrong]), clock_ms=lambda: NOW_MS)
        with self.assertRaises(ValueError):
            reader.read(incident_id="incident-1")

        malformed = document(1)
        malformed["unexpected"] = "do-not-promote"
        reader = GoogleCloudAuditReader(FakeLogger([malformed]), clock_ms=lambda: NOW_MS)
        with self.assertRaises(ValueError):
            reader.read(incident_id="incident-1")

        empty = GoogleCloudAuditReader(FakeLogger([]), clock_ms=lambda: NOW_MS)
        for limit in (0, 102):
            with self.subTest(limit=limit):
                with self.assertRaises(ValueError):
                    empty.read(incident_id="incident-1", limit=limit)
        with self.assertRaises(ValueError):
            empty.read(incident_id="incident-1", after_sequence=-1)
        with self.assertRaises(ValueError):
            empty.read_candidates(incident_id="incident-1", through_sequence=-1)
        with self.assertRaises(ValueError):
            empty.read_candidates(incident_id="incident-1", through_sequence=1, limit=4097)

    def test_reader_rejects_old_future_and_conflicting_duplicate_entries(self):
        old = document(1)
        old["timestamp_unix_ms"] = NOW_MS - 3_600_001
        with self.assertRaises(ValueError):
            GoogleCloudAuditReader(
                FakeLogger([old]), lookback_seconds=3600, clock_ms=lambda: NOW_MS
            ).read(incident_id="incident-1")

        future = document(1)
        future["timestamp_unix_ms"] = NOW_MS + 60_001
        with self.assertRaises(ValueError):
            GoogleCloudAuditReader(FakeLogger([future]), clock_ms=lambda: NOW_MS).read(
                incident_id="incident-1"
            )

        first = document(1)
        second = document(1)
        second["actor"] = "different@example.com"
        with self.assertRaises(ValueError):
            GoogleCloudAuditReader(FakeLogger([first, second]), clock_ms=lambda: NOW_MS).read(
                incident_id="incident-1"
            )


class DurableTimelineMergeTests(unittest.TestCase):
    def test_service_merges_durable_and_local_events_without_exposing_extra_fields(self):
        durable = AuditEvent(
            2,
            NOW_MS + 1,
            "incident-1",
            "remediation_approved",
            "operator@example.com",
            {
                "revision": "rev-1",
                "action": "recover_uplink",
                "target": "private-target",
                "activation_profile_sha256": "private",
            },
        )

        class Reader:
            def read(self, **_kwargs):
                return [durable]

        service = IncidentService(
            Metrics(),
            Remediation(),
            MemoryAuditLog(),
            audit_reader=Reader(),
            id_factory=lambda: "incident-1",
            clock_ms=lambda: NOW_MS,
        )
        service.investigate(actor="operator@example.com")

        timeline = service.audit_timeline(incident_id="incident-1", limit=10)
        self.assertEqual([1, 2], [event["sequence"] for event in timeline["events"]])
        payload = timeline["events"][1]["payload"]
        self.assertEqual("recover_uplink", payload["action"])
        self.assertNotIn("target", payload)
        self.assertNotIn("activation_profile_sha256", payload)

    def test_service_fails_closed_on_conflicting_durable_and_local_sequence(self):
        class Reader:
            def read(self, **_kwargs):
                return [
                    AuditEvent(
                        1,
                        NOW_MS,
                        "incident-1",
                        "investigation_completed",
                        "different-actor",
                        {"revision": "different"},
                    )
                ]

        service = IncidentService(
            Metrics(),
            Remediation(),
            MemoryAuditLog(),
            audit_reader=Reader(),
            id_factory=lambda: "incident-1",
            clock_ms=lambda: NOW_MS,
        )
        service.investigate(actor="operator@example.com")
        with self.assertRaises(RuntimeError):
            service.audit_timeline(incident_id="incident-1")


if __name__ == "__main__":
    unittest.main()

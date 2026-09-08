from __future__ import annotations

import unittest
from types import SimpleNamespace

from durable_audit_reader import GoogleCloudAuditReader


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


def document(sequence: int, *, actor: str = "winner@example.com") -> dict:
    return {
        "schema": "stageguard.audit.v1",
        "sequence": sequence,
        "timestamp_unix_ms": NOW_MS - 1_000 + sequence,
        "incident_id": "incident-1",
        "event_type": "investigation_completed",
        "actor": actor,
        "payload": {"revision": f"rev-{sequence}"},
    }


class AnchoredCloudAuditReaderTests(unittest.TestCase):
    def test_candidate_range_starts_exclusively_after_authenticated_anchor(self):
        logger = FakeLogger([document(1025), document(1026)])
        reader = GoogleCloudAuditReader(logger, lookback_seconds=3600, clock_ms=lambda: NOW_MS)

        candidates = reader.read_candidates(
            incident_id="incident-1",
            after_sequence=1024,
            through_sequence=1026,
            limit=10,
        )

        self.assertEqual([1025, 1026], [event.sequence for event in candidates])
        call = logger.calls[0]
        self.assertIn("jsonPayload.sequence>1024", call["filter_"])
        self.assertIn("jsonPayload.sequence<=1026", call["filter_"])
        self.assertNotIn("jsonPayload.sequence>0 ", call["filter_"])
        self.assertEqual(11, call["max_results"])

    def test_candidate_range_preserves_post_anchor_competitors(self):
        logger = FakeLogger([
            document(1025, actor="winner@example.com"),
            document(1025, actor="loser@example.com"),
            document(1026),
        ])
        reader = GoogleCloudAuditReader(logger, clock_ms=lambda: NOW_MS)

        candidates = reader.read_candidates(
            incident_id="incident-1",
            after_sequence=1024,
            through_sequence=1026,
            limit=10,
        )

        self.assertEqual([1025, 1025, 1026], [event.sequence for event in candidates])
        self.assertEqual(
            {"winner@example.com", "loser@example.com"},
            {event.actor for event in candidates if event.sequence == 1025},
        )

    def test_candidate_range_rejects_entries_at_or_before_anchor(self):
        reader = GoogleCloudAuditReader(FakeLogger([document(1024)]), clock_ms=lambda: NOW_MS)
        with self.assertRaisesRegex(ValueError, "requested range"):
            reader.read_candidates(
                incident_id="incident-1",
                after_sequence=1024,
                through_sequence=1026,
                limit=10,
            )

    def test_empty_and_invalid_anchor_ranges_are_bounded(self):
        logger = FakeLogger([])
        reader = GoogleCloudAuditReader(logger, clock_ms=lambda: NOW_MS)
        self.assertEqual(
            [],
            reader.read_candidates(
                incident_id="incident-1", after_sequence=10, through_sequence=10
            ),
        )
        self.assertEqual([], logger.calls)

        with self.assertRaisesRegex(ValueError, "lower bound"):
            reader.read_candidates(
                incident_id="incident-1", after_sequence=11, through_sequence=10
            )
        with self.assertRaisesRegex(ValueError, "after_sequence"):
            reader.read_candidates(
                incident_id="incident-1", after_sequence=-1, through_sequence=10
            )


if __name__ == "__main__":
    unittest.main()

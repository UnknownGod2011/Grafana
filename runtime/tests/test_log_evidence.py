#!/usr/bin/env python3
import unittest

from log_evidence import (
    LogQueryResult,
    LogRecord,
    MAX_CORROBORATION_LINES,
    corroborate_uplink_loss,
    uplink_loss_logql,
)
from telemetry import DEFAULT_TELEMETRY_PROFILE, TelemetryProfile


class FakeLogs:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def range(self, logql, *, start, end, limit):
        self.calls.append((logql, start, end, limit))
        return self.result


def record(*, production="broadcast-alpha", uplink="uplink-b", event="packet_loss_alarm"):
    return LogRecord(
        timestamp="1760000000000000000",
        line='{"event":"%s"}' % event,
        labels={"production_id": production, "uplink": uplink},
        structured_metadata={},
        parsed={"event": event},
    )


class LogEvidenceTests(unittest.TestCase):
    def test_query_is_policy_owned_and_scope_bound(self):
        profile = TelemetryProfile(production_id='show"one', affected_uplink="uplink-z")
        query = uplink_loss_logql(profile)
        self.assertIn('production_id="show\\"one"', query)
        self.assertIn('uplink="uplink-z"', query)
        self.assertIn('| json | event="packet_loss_alarm"', query)

    def test_complete_matching_log_corroborates(self):
        client = FakeLogs(LogQueryResult((record(),), False, "now-5m", "now"))
        evidence = corroborate_uplink_loss(client, DEFAULT_TELEMETRY_PROFILE)
        self.assertEqual("corroborated", evidence.status)
        self.assertTrue(evidence.supports_hypothesis)
        self.assertEqual(1, len(client.calls))
        self.assertEqual(MAX_CORROBORATION_LINES, client.calls[0][3])

    def test_missing_log_is_missing_not_negative_evidence(self):
        client = FakeLogs(LogQueryResult((), False, "now-5m", "now"))
        evidence = corroborate_uplink_loss(client, DEFAULT_TELEMETRY_PROFILE)
        self.assertEqual("missing", evidence.status)
        self.assertIsNone(evidence.supports_hypothesis)

    def test_truncated_result_fails_closed(self):
        client = FakeLogs(LogQueryResult((record(),), True, "now-5m", "now"))
        self.assertEqual("ambiguous", corroborate_uplink_loss(client, DEFAULT_TELEMETRY_PROFILE).status)

    def test_scope_drift_fails_closed(self):
        client = FakeLogs(LogQueryResult((record(uplink="uplink-a"),), False, "now-5m", "now"))
        self.assertEqual("ambiguous", corroborate_uplink_loss(client, DEFAULT_TELEMETRY_PROFILE).status)

    def test_event_drift_fails_closed(self):
        client = FakeLogs(LogQueryResult((record(event="link_restored"),), False, "now-5m", "now"))
        self.assertEqual("ambiguous", corroborate_uplink_loss(client, DEFAULT_TELEMETRY_PROFILE).status)

    def test_non_result_envelope_fails_closed(self):
        evidence = corroborate_uplink_loss(FakeLogs({"records": []}), DEFAULT_TELEMETRY_PROFILE)
        self.assertEqual("ambiguous", evidence.status)
        self.assertIn("malformed result envelope", evidence.reason)

    def test_non_boolean_truncation_marker_fails_closed(self):
        evidence = corroborate_uplink_loss(
            FakeLogs(LogQueryResult((record(),), 1, "now-5m", "now")),
            DEFAULT_TELEMETRY_PROFILE,
        )
        self.assertEqual("ambiguous", evidence.status)
        self.assertIn("truncation marker", evidence.reason)

    def test_query_window_drift_fails_closed(self):
        for result in (
            LogQueryResult((record(),), False, "now-10m", "now"),
            LogQueryResult((record(),), False, "now-5m", "now-1m"),
        ):
            with self.subTest(start=result.start, end=result.end):
                evidence = corroborate_uplink_loss(FakeLogs(result), DEFAULT_TELEMETRY_PROFILE)
                self.assertEqual("ambiguous", evidence.status)
                self.assertIn("window disagreed", evidence.reason)

    def test_non_string_window_fails_closed(self):
        evidence = corroborate_uplink_loss(
            FakeLogs(LogQueryResult((record(),), False, None, "now")),  # type: ignore[arg-type]
            DEFAULT_TELEMETRY_PROFILE,
        )
        self.assertEqual("ambiguous", evidence.status)
        self.assertIn("invalid evidence window", evidence.reason)

    def test_non_tuple_records_fail_closed(self):
        evidence = corroborate_uplink_loss(
            FakeLogs(LogQueryResult([record()], False, "now-5m", "now")),  # type: ignore[arg-type]
            DEFAULT_TELEMETRY_PROFILE,
        )
        self.assertEqual("ambiguous", evidence.status)
        self.assertIn("record collection", evidence.reason)

    def test_over_budget_records_fail_closed(self):
        result = LogQueryResult(
            tuple(record() for _ in range(MAX_CORROBORATION_LINES + 1)),
            False,
            "now-5m",
            "now",
        )
        evidence = corroborate_uplink_loss(FakeLogs(result), DEFAULT_TELEMETRY_PROFILE)
        self.assertEqual("ambiguous", evidence.status)
        self.assertIn("record collection", evidence.reason)

    def test_malformed_record_fields_fail_closed(self):
        malformed = (
            LogRecord("", '{"event":"packet_loss_alarm"}', {"production_id": "broadcast-alpha", "uplink": "uplink-b"}, {}, {"event": "packet_loss_alarm"}),
            LogRecord("1760000000000000000", '{"event":"packet_loss_alarm"}', {"production_id": 7, "uplink": "uplink-b"}, {}, {"event": "packet_loss_alarm"}),  # type: ignore[dict-item]
            LogRecord("1760000000000000000", '{"event":"packet_loss_alarm"}', {"production_id": "broadcast-alpha", "uplink": "uplink-b"}, [], {"event": "packet_loss_alarm"}),  # type: ignore[arg-type]
            LogRecord("1760000000000000000", None, {"production_id": "broadcast-alpha", "uplink": "uplink-b"}, {}, {"event": "packet_loss_alarm"}),  # type: ignore[arg-type]
        )
        for bad_record in malformed:
            with self.subTest(record=bad_record):
                evidence = corroborate_uplink_loss(
                    FakeLogs(LogQueryResult((bad_record,), False, "now-5m", "now")),
                    DEFAULT_TELEMETRY_PROFILE,
                )
                self.assertEqual("ambiguous", evidence.status)
                self.assertIn("malformed log record", evidence.reason)


if __name__ == "__main__":
    unittest.main()

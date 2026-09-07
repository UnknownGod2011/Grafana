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
    def __init__(self, result: LogQueryResult):
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


if __name__ == "__main__":
    unittest.main()

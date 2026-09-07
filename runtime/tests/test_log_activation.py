from __future__ import annotations

import pathlib
import tempfile
import unittest

import sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from log_activation import (
    create_log_activation_record,
    load_log_activation_record,
    log_contract_sha256,
    preflight_loki,
    verify_log_activation_record,
    write_log_activation_record,
)
from log_evidence import LogQueryResult, LogRecord
from telemetry import TelemetryProfile


def profile() -> TelemetryProfile:
    return TelemetryProfile(
        production_id="prod-42",
        affected_feed="hero-cam",
        affected_uplink="primary-wan",
        healthy_uplink="backup-wan",
        healthy_peer_feeds=("cam-a", "cam-b"),
        dropped_frames_metric="media_frames_dropped_total",
        packet_loss_metric="media_packet_loss_percent",
        cpu_metric="media_encoder_cpu_percent",
        gpu_metric="media_encoder_gpu_percent",
        production_label="production",
        feed_label="feed",
        uplink_label="uplink",
    )


class FakeLogs:
    def __init__(self, result: LogQueryResult | None = None) -> None:
        self.result = result
        self.calls = []

    def range(self, logql: str, *, start: str, end: str, limit: int) -> LogQueryResult:
        self.calls.append((logql, start, end, limit))
        return self.result or LogQueryResult((), False, start, end)


class LogActivationTests(unittest.TestCase):
    def test_empty_healthy_window_can_preflight_and_round_trip(self) -> None:
        p = profile()
        preflight = preflight_loki(FakeLogs(), p)
        self.assertTrue(preflight.ready)
        self.assertEqual(1, len(FakeLogs().calls) + 1)  # sanity: fixture remains side-effect free
        record = create_log_activation_record(p, "loki-main", preflight, now_unix=1000)
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "log-activation.json"
            write_log_activation_record(path, record)
            loaded = load_log_activation_record(path)
        self.assertEqual(record, loaded)
        verify_log_activation_record(loaded, p, "loki-main", now_unix=1001)

    def test_preflight_executes_exact_policy_contract(self) -> None:
        p = profile()
        client = FakeLogs()
        result = preflight_loki(client, p)
        self.assertTrue(result.ready)
        self.assertEqual(1, len(client.calls))
        logql, start, end, limit = client.calls[0]
        self.assertEqual(result.query, logql)
        self.assertEqual(result.start, start)
        self.assertEqual(result.end, end)
        self.assertEqual(result.limit, limit)

    def test_truncated_preflight_cannot_activate(self) -> None:
        p = profile()
        client = FakeLogs(LogQueryResult((), True, "now-5m", "now"))
        preflight = preflight_loki(client, p)
        self.assertFalse(preflight.ready)
        with self.assertRaisesRegex(ValueError, "did not pass preflight"):
            create_log_activation_record(p, "loki-main", preflight, now_unix=1000)

    def test_scope_drift_fails_preflight(self) -> None:
        p = profile()
        record = LogRecord(
            "2026-09-07T00:00:00Z",
            '{"event":"packet_loss_alarm"}',
            {"production": "other-prod", "uplink": "primary-wan"},
            {},
            {},
        )
        preflight = preflight_loki(
            FakeLogs(LogQueryResult((record,), False, "now-5m", "now")), p
        )
        self.assertFalse(preflight.ready)
        self.assertEqual("ambiguous", preflight.status)

    def test_datasource_drift_is_rejected(self) -> None:
        p = profile()
        preflight = preflight_loki(FakeLogs(), p)
        activation = create_log_activation_record(p, "loki-main", preflight, now_unix=1000)
        with self.assertRaisesRegex(ValueError, "datasource identity changed"):
            verify_log_activation_record(activation, p, "loki-other", now_unix=1001)

    def test_contract_drift_is_rejected(self) -> None:
        p = profile()
        preflight = preflight_loki(FakeLogs(), p)
        activation = create_log_activation_record(p, "loki-main", preflight, now_unix=1000)
        changed = TelemetryProfile(**{**p.__dict__, "affected_uplink": "other-wan"})
        self.assertNotEqual(log_contract_sha256(p), log_contract_sha256(changed))
        with self.assertRaisesRegex(ValueError, "contract changed"):
            verify_log_activation_record(activation, changed, "loki-main", now_unix=1001)

    def test_stale_log_activation_is_rejected(self) -> None:
        p = profile()
        preflight = preflight_loki(FakeLogs(), p)
        activation = create_log_activation_record(
            p, "loki-main", preflight, now_unix=1000, ttl_seconds=10
        )
        with self.assertRaisesRegex(ValueError, "stale"):
            verify_log_activation_record(activation, p, "loki-main", now_unix=1010)


if __name__ == "__main__":
    unittest.main()

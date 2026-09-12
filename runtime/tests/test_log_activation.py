from __future__ import annotations

import json
import pathlib
import tempfile
import unittest

import sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from evidence_errors import EvidenceUnavailable
from log_activation import (
    LOG_ACTIVATION_VERSION,
    MAX_TTL_SECONDS,
    LogActivationRecord,
    LogPreflightResult,
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


class EvidenceFailingLogs:
    def range(self, logql: str, *, start: str, end: str, limit: int) -> LogQueryResult:
        raise EvidenceUnavailable("https://grafana.example/?token=super-secret-provider-value")


class ProgrammingFailingLogs:
    def range(self, logql: str, *, start: str, end: str, limit: int) -> LogQueryResult:
        raise AssertionError("programming contract broken")


class LogActivationTests(unittest.TestCase):
    def test_empty_healthy_window_can_preflight_and_round_trip(self) -> None:
        p = profile()
        client = FakeLogs()
        preflight = preflight_loki(client, p)
        self.assertTrue(preflight.ready)
        self.assertEqual(1, len(client.calls))
        record = create_log_activation_record(p, "loki-main", preflight, now_unix=1000)
        self.assertEqual(LOG_ACTIVATION_VERSION, record.version)
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

    def test_evidence_failure_is_redacted_and_non_ready(self) -> None:
        result = preflight_loki(EvidenceFailingLogs(), profile())
        self.assertFalse(result.ready)
        self.assertEqual("error", result.status)
        self.assertEqual("evidence source unavailable", result.detail)
        serialized = json.dumps(result.to_dict())
        self.assertNotIn("super-secret-provider-value", serialized)
        self.assertNotIn("grafana.example", serialized)

    def test_unexpected_programming_failure_propagates(self) -> None:
        with self.assertRaisesRegex(AssertionError, "programming contract broken"):
            preflight_loki(ProgrammingFailingLogs(), profile())

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

    def test_forged_ok_preflight_cannot_carry_detail(self) -> None:
        p = profile()
        preflight = preflight_loki(FakeLogs(), p)
        forged = LogPreflightResult(**{**preflight.to_dict(), "detail": "provider warning"})
        with self.assertRaisesRegex(ValueError, "without error detail"):
            create_log_activation_record(p, "loki-main", forged, now_unix=1000)

    def test_forged_ok_preflight_line_count_is_bounded(self) -> None:
        p = profile()
        preflight = preflight_loki(FakeLogs(), p)
        for value in (-1, preflight.limit + 1, True, 1.5):
            with self.subTest(value=value):
                forged = LogPreflightResult(**{**preflight.to_dict(), "line_count": value})
                with self.assertRaisesRegex(ValueError, "line_count"):
                    create_log_activation_record(p, "loki-main", forged, now_unix=1000)

    def test_forged_ok_preflight_window_text_is_bounded(self) -> None:
        p = profile()
        preflight = preflight_loki(FakeLogs(), p)
        for mutation in ({"start": ""}, {"end": "now\nforged"}, {"start": "x" * 257}):
            with self.subTest(mutation=mutation):
                forged = LogPreflightResult(**{**preflight.to_dict(), **mutation})
                with self.assertRaises(ValueError):
                    create_log_activation_record(p, "loki-main", forged, now_unix=1000)

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

    def test_legacy_log_activation_version_is_rejected(self) -> None:
        p = profile()
        current = create_log_activation_record(p, "loki-main", preflight_loki(FakeLogs(), p), now_unix=1000)
        legacy = LogActivationRecord(**{**current.to_dict(), "version": LOG_ACTIVATION_VERSION - 1})
        with self.assertRaisesRegex(ValueError, "unsupported Loki activation version"):
            verify_log_activation_record(legacy, p, "loki-main", now_unix=1001)

    def test_verify_rejects_manually_extended_lifetime(self) -> None:
        p = profile()
        current = create_log_activation_record(p, "loki-main", preflight_loki(FakeLogs(), p), now_unix=1000)
        forged = LogActivationRecord(
            **{**current.to_dict(), "expires_at_unix": current.created_at_unix + MAX_TTL_SECONDS + 1}
        )
        with self.assertRaisesRegex(ValueError, "lifetime exceeds"):
            verify_log_activation_record(forged, p, "loki-main", now_unix=1001)

    def test_load_rejects_noncanonical_digest_and_invalid_lifetime(self) -> None:
        p = profile()
        current = create_log_activation_record(p, "loki-main", preflight_loki(FakeLogs(), p), now_unix=1000)
        mutations = (
            {"preflight_sha256": "A" * 64},
            {"contract_sha256": "g" * 64},
            {"datasource_sha256": "0" * 63},
            {"created_at_unix": -1},
            {"expires_at_unix": current.created_at_unix},
            {"expires_at_unix": current.created_at_unix + MAX_TTL_SECONDS + 1},
        )
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "log-activation.json"
            for mutation in mutations:
                with self.subTest(mutation=mutation):
                    path.write_text(json.dumps({**current.to_dict(), **mutation}), encoding="utf-8")
                    with self.assertRaises(ValueError):
                        load_log_activation_record(path)

    def test_write_revalidates_manually_constructed_record(self) -> None:
        p = profile()
        current = create_log_activation_record(p, "loki-main", preflight_loki(FakeLogs(), p), now_unix=1000)
        forged = LogActivationRecord(**{**current.to_dict(), "production_id": " prod-42"})
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "log-activation.json"
            with self.assertRaisesRegex(ValueError, "boundary whitespace"):
                write_log_activation_record(path, forged)
            self.assertFalse(path.exists())

    def test_creation_and_verification_reject_invalid_explicit_clock(self) -> None:
        p = profile()
        preflight = preflight_loki(FakeLogs(), p)
        current = create_log_activation_record(p, "loki-main", preflight, now_unix=1000)
        for value in (True, -1, 1.5, "1000"):
            with self.subTest(value=repr(value)):
                with self.assertRaisesRegex(ValueError, "now_unix"):
                    create_log_activation_record(p, "loki-main", preflight, now_unix=value)
                with self.assertRaisesRegex(ValueError, "now_unix"):
                    verify_log_activation_record(current, p, "loki-main", now_unix=value)


if __name__ == "__main__":
    unittest.main()

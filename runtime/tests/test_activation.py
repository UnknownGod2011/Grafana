import math
import pathlib
import tempfile
import unittest

import sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from activation import (
    create_activation_record,
    load_activation_record,
    verify_activation_record,
    write_activation_record,
)
from incident_service import IncidentService, MemoryAuditLog
from onboarding import PreflightResult, PreflightSlot, preflight_telemetry
from remediation import ActionResult
from telemetry import TelemetryProfile, investigation_queries, recovery_queries


class RecordingClient:
    def __init__(self, values):
        self.values = values
        self.calls = []

    def instant(self, promql):
        self.calls.append(promql)
        return self.values.get(promql)


class FakeRemediation:
    def recover_uplink(self, production_id, uplink):
        return ActionResult(True, "ok")


def profile():
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


def successful_preflight(p):
    queries = [q for q, _ in investigation_queries(p).values()]
    queries += [q for q, _ in recovery_queries(p).values()]
    return preflight_telemetry(RecordingClient({q: 1.0 for q in queries}), p)


def forged_preflight(p, *, value=1.0, detail=None):
    slots = tuple(
        PreflightSlot(
            phase="investigation" if index < 5 else "recovery",
            name=f"slot-{index}",
            promql=f"vector({index})",
            status="ok",
            value=value,
            detail=detail,
        )
        for index in range(8)
    )
    return PreflightResult(production_id=p.production_id, ready=True, slots=slots)


class ActivationTests(unittest.TestCase):
    def test_successful_preflight_can_be_pinned_and_round_tripped(self):
        p = profile()
        record = create_activation_record(p, "prom-main", successful_preflight(p), now_unix=1000)
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "activation.json"
            write_activation_record(path, record)
            loaded = load_activation_record(path)
        self.assertEqual(record, loaded)
        verify_activation_record(loaded, p, "prom-main", now_unix=1001)

    def test_failed_preflight_cannot_create_activation(self):
        p = profile()
        queries = [q for q, _ in investigation_queries(p).values()]
        queries += [q for q, _ in recovery_queries(p).values()]
        result = preflight_telemetry(RecordingClient({q: None for q in queries}), p)
        with self.assertRaisesRegex(ValueError, "did not pass preflight"):
            create_activation_record(p, "prom-main", result, now_unix=1000)

    def test_forged_ok_preflight_requires_numeric_samples(self):
        p = profile()
        for value in (None, True, "1.0"):
            with self.subTest(value=repr(value)):
                with self.assertRaisesRegex(ValueError, "numeric sample"):
                    create_activation_record(
                        p,
                        "prom-main",
                        forged_preflight(p, value=value),
                        now_unix=1000,
                    )

    def test_forged_ok_preflight_requires_finite_samples(self):
        p = profile()
        for value in (math.nan, math.inf, -math.inf):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "finite sample"):
                    create_activation_record(
                        p,
                        "prom-main",
                        forged_preflight(p, value=value),
                        now_unix=1000,
                    )

    def test_forged_ok_preflight_cannot_carry_error_detail(self):
        p = profile()
        with self.assertRaisesRegex(ValueError, "without error detail"):
            create_activation_record(
                p,
                "prom-main",
                forged_preflight(p, detail="provider warning"),
                now_unix=1000,
            )

    def test_profile_change_after_preflight_is_rejected(self):
        p = profile()
        record = create_activation_record(p, "prom-main", successful_preflight(p), now_unix=1000)
        changed = TelemetryProfile(**{**p.__dict__, "affected_feed": "other-cam"})
        with self.assertRaisesRegex(ValueError, "profile changed"):
            verify_activation_record(record, changed, "prom-main", now_unix=1001)

    def test_datasource_change_after_preflight_is_rejected(self):
        p = profile()
        record = create_activation_record(p, "prom-main", successful_preflight(p), now_unix=1000)
        with self.assertRaisesRegex(ValueError, "datasource identity changed"):
            verify_activation_record(record, p, "prom-other", now_unix=1001)

    def test_stale_activation_is_rejected(self):
        p = profile()
        record = create_activation_record(
            p, "prom-main", successful_preflight(p), now_unix=1000, ttl_seconds=10
        )
        with self.assertRaisesRegex(ValueError, "stale"):
            verify_activation_record(record, p, "prom-main", now_unix=1010)

    def test_non_default_incident_service_refuses_unactivated_profile(self):
        p = profile()
        with self.assertRaisesRegex(ValueError, "require a successful activation"):
            IncidentService(RecordingClient({}), FakeRemediation(), MemoryAuditLog(), telemetry_profile=p)

    def test_incident_service_accepts_matching_activation(self):
        p = profile()
        record = create_activation_record(p, "prom-main", successful_preflight(p), now_unix=1000)
        service = IncidentService(
            RecordingClient({}),
            FakeRemediation(),
            MemoryAuditLog(),
            telemetry_profile=p,
            activation_record=record,
            datasource_identity="prom-main",
            activation_now_unix=1001,
        )
        self.assertIsNone(service.status())


if __name__ == "__main__":
    unittest.main()

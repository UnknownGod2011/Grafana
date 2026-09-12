import json
import math
import pathlib
import tempfile
import unittest

import sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from activation import (
    ACTIVATION_VERSION,
    MAX_TTL_SECONDS,
    ActivationRecord,
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


def successful_preflight(p, value=1.0):
    queries = [q for q, _ in investigation_queries(p).values()]
    queries += [q for q, _ in recovery_queries(p).values()]
    return preflight_telemetry(RecordingClient({q: value for q in queries}), p)


def forged_preflight(p, *, value=1.0, detail=None):
    slots = []
    for phase, queries in (
        ("investigation", investigation_queries(p)),
        ("recovery", recovery_queries(p)),
    ):
        for name, (promql, _expectation) in queries.items():
            slots.append(
                PreflightSlot(
                    phase=phase,
                    name=name,
                    promql=promql,
                    status="ok",
                    value=value,
                    detail=detail,
                )
            )
    return PreflightResult(production_id=p.production_id, ready=True, slots=tuple(slots))


class ActivationTests(unittest.TestCase):
    def test_successful_preflight_can_be_pinned_and_round_tripped(self):
        p = profile()
        record = create_activation_record(p, "prom-main", successful_preflight(p), now_unix=1000)
        self.assertEqual(ACTIVATION_VERSION, record.version)
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

    def test_forged_ok_preflight_with_arbitrary_promql_is_rejected(self):
        p = profile()
        forged = PreflightResult(
            production_id=p.production_id,
            ready=True,
            slots=tuple(
                PreflightSlot(
                    phase="investigation" if index < 6 else "recovery",
                    name=f"forged-{index}",
                    promql=f"vector({index})",
                    status="ok",
                    value=1.0,
                )
                for index in range(8)
            ),
        )
        with self.assertRaisesRegex(ValueError, "contract does not match"):
            create_activation_record(p, "prom-main", forged, now_unix=1000)

    def test_forged_ok_preflight_with_reordered_real_slots_is_rejected(self):
        p = profile()
        original = successful_preflight(p)
        forged = PreflightResult(
            production_id=p.production_id,
            ready=True,
            slots=tuple(reversed(original.slots)),
        )
        with self.assertRaisesRegex(ValueError, "contract does not match"):
            create_activation_record(p, "prom-main", forged, now_unix=1000)

    def test_activation_digest_binds_observed_sample_values(self):
        p = profile()
        first = create_activation_record(p, "prom-main", successful_preflight(p, 1.0), now_unix=1000)
        second = create_activation_record(p, "prom-main", successful_preflight(p, 2.0), now_unix=1000)
        self.assertNotEqual(first.slot_digest_sha256, second.slot_digest_sha256)

    def test_legacy_activation_version_is_rejected(self):
        p = profile()
        current = create_activation_record(p, "prom-main", successful_preflight(p), now_unix=1000)
        legacy = ActivationRecord(**{**current.to_dict(), "version": ACTIVATION_VERSION - 1})
        with self.assertRaisesRegex(ValueError, "unsupported activation"):
            verify_activation_record(legacy, p, "prom-main", now_unix=1001)

    def test_creation_rejects_invalid_explicit_clock(self):
        p = profile()
        preflight = successful_preflight(p)
        for value in (True, -1, 1.5, "1000"):
            with self.subTest(value=repr(value)):
                with self.assertRaisesRegex(ValueError, "now_unix"):
                    create_activation_record(p, "prom-main", preflight, now_unix=value)

    def test_verify_rejects_manually_extended_lifetime(self):
        p = profile()
        record = create_activation_record(p, "prom-main", successful_preflight(p), now_unix=1000)
        forged = ActivationRecord(
            **{
                **record.to_dict(),
                "expires_at_unix": record.created_at_unix + MAX_TTL_SECONDS + 1,
            }
        )
        with self.assertRaisesRegex(ValueError, "lifetime exceeds"):
            verify_activation_record(forged, p, "prom-main", now_unix=1001)

    def test_load_rejects_noncanonical_sha256_fields(self):
        p = profile()
        record = create_activation_record(p, "prom-main", successful_preflight(p), now_unix=1000)
        mutations = (
            ("profile_sha256", "A" * 64),
            ("datasource_sha256", "g" * 64),
            ("slot_digest_sha256", "0" * 63),
        )
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "activation.json"
            for field, value in mutations:
                with self.subTest(field=field):
                    path.write_text(
                        json.dumps({**record.to_dict(), field: value}),
                        encoding="utf-8",
                    )
                    with self.assertRaisesRegex(ValueError, "canonical SHA-256"):
                        load_activation_record(path)

    def test_load_rejects_invalid_timestamp_relationships(self):
        p = profile()
        record = create_activation_record(p, "prom-main", successful_preflight(p), now_unix=1000)
        mutations = (
            {"created_at_unix": -1},
            {"expires_at_unix": record.created_at_unix},
            {"expires_at_unix": record.created_at_unix + MAX_TTL_SECONDS + 1},
        )
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "activation.json"
            for mutation in mutations:
                with self.subTest(mutation=mutation):
                    path.write_text(
                        json.dumps({**record.to_dict(), **mutation}),
                        encoding="utf-8",
                    )
                    with self.assertRaises(ValueError):
                        load_activation_record(path)

    def test_write_revalidates_manually_constructed_record(self):
        p = profile()
        record = create_activation_record(p, "prom-main", successful_preflight(p), now_unix=1000)
        forged = ActivationRecord(**{**record.to_dict(), "production_id": " prod-42"})
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "activation.json"
            with self.assertRaisesRegex(ValueError, "boundary whitespace"):
                write_activation_record(path, forged)
            self.assertFalse(path.exists())

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

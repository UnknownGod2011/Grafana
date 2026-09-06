from __future__ import annotations

import json
import os
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from activation import create_activation_record, write_activation_record
from bootstrap import DisabledRemediationClient, build_runtime
from onboarding import PreflightResult, PreflightSlot, load_telemetry_profile
from telemetry import investigation_queries, recovery_queries


class FakeMetrics:
    def __init__(self, datasource_uid: str = "prom-main") -> None:
        self.datasource_uid = datasource_uid
        self.closed = False

    def instant(self, _promql: str) -> float:
        return 1.0

    def close(self) -> None:
        self.closed = True


@contextmanager
def clean_auth_env():
    with patch.dict(os.environ, {}, clear=False):
        old_token = os.environ.pop("STAGEGUARD_API_TOKEN", None)
        old_subject = os.environ.pop("STAGEGUARD_API_SUBJECT", None)
        try:
            yield
        finally:
            if old_token is not None:
                os.environ["STAGEGUARD_API_TOKEN"] = old_token
            if old_subject is not None:
                os.environ["STAGEGUARD_API_SUBJECT"] = old_subject


class BootstrapTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _write_profile(self, production_id: str = "prod-real") -> Path:
        document = {
            "version": 1,
            "profile": {
                "production_id": production_id,
                "affected_feed": "camera-main",
                "affected_uplink": "primary-uplink",
                "healthy_uplink": "backup-uplink",
                "healthy_peer_feeds": ["camera-a", "camera-b"],
                "dropped_frames_metric": "studio_frames_dropped_total",
                "packet_loss_metric": "studio_packet_loss_percent",
                "cpu_metric": "studio_encoder_cpu_percent",
                "gpu_metric": "studio_encoder_gpu_percent",
                "production_label": "production",
                "feed_label": "feed",
                "uplink_label": "uplink"
            },
        }
        path = self.root / "telemetry.json"
        path.write_text(json.dumps(document), encoding="utf-8")
        return path

    def _activation(self, config: Path, datasource_uid: str = "prom-main") -> Path:
        profile = load_telemetry_profile(config)
        slots = []
        for phase, queries in (
            ("investigation", investigation_queries(profile)),
            ("recovery", recovery_queries(profile)),
        ):
            for name, (promql, _expectation) in queries.items():
                slots.append(PreflightSlot(phase, name, promql, "ok", 1.0))
        preflight = PreflightResult(profile.production_id, True, tuple(slots))
        record = create_activation_record(
            profile,
            datasource_uid,
            preflight,
            now_unix=1_800_000_000,
            ttl_seconds=3600,
        )
        path = self.root / "activation.json"
        write_activation_record(path, record)
        return path

    def test_production_profile_refuses_startup_without_activation(self) -> None:
        config = self._write_profile()
        metrics = FakeMetrics()
        with self.assertRaisesRegex(ValueError, "requires --activation"):
            build_runtime(
                telemetry_config=config,
                activation_path=None,
                audit_path=self.root / "audit.jsonl",
                metrics_factory=lambda: metrics,
                activation_now_unix=1_800_000_100,
                port=0,
            )
        self.assertTrue(metrics.closed)

    def test_activation_is_verified_against_actual_mcp_datasource_identity(self) -> None:
        config = self._write_profile()
        activation = self._activation(config, "prom-approved")
        metrics = FakeMetrics("prom-drifted")
        with self.assertRaisesRegex(ValueError, "datasource identity changed"):
            build_runtime(
                telemetry_config=config,
                activation_path=activation,
                audit_path=self.root / "audit.jsonl",
                metrics_factory=lambda: metrics,
                activation_now_unix=1_800_000_100,
                port=0,
            )
        self.assertTrue(metrics.closed)

    def test_non_loopback_requires_process_owned_bearer_token(self) -> None:
        # Reuse the repository's demo profile shape so activation is not the
        # reason startup is refused; this isolates the network/auth boundary.
        example = Path(__file__).parents[1] / "telemetry.example.json"
        with clean_auth_env(), self.assertRaisesRegex(ValueError, "STAGEGUARD_API_TOKEN"):
            build_runtime(
                telemetry_config=example,
                activation_path=None,
                audit_path=self.root / "audit.jsonl",
                host="0.0.0.0",
                port=0,
                metrics_factory=FakeMetrics,
            )

    def test_loopback_defaults_to_local_identity(self) -> None:
        example = Path(__file__).parents[1] / "telemetry.example.json"
        with clean_auth_env():
            bundle = build_runtime(
                telemetry_config=example,
                activation_path=None,
                audit_path=self.root / "audit.jsonl",
                host="127.0.0.1",
                port=0,
                metrics_factory=FakeMetrics,
            )
        try:
            self.assertTrue(bundle.identity_provider.is_development_only)
            self.assertTrue((self.root / "audit.jsonl").exists())
        finally:
            bundle.close()

    def test_production_runtime_uses_safe_disabled_remediation_by_default(self) -> None:
        config = self._write_profile()
        activation = self._activation(config)
        with patch.dict(
            os.environ,
            {"STAGEGUARD_API_TOKEN": "secret", "STAGEGUARD_API_SUBJECT": "ops@example"},
            clear=False,
        ):
            bundle = build_runtime(
                telemetry_config=config,
                activation_path=activation,
                audit_path=self.root / "audit.jsonl",
                host="0.0.0.0",
                port=0,
                metrics_factory=FakeMetrics,
                activation_now_unix=1_800_000_100,
            )
        try:
            self.assertFalse(bundle.identity_provider.is_development_only)
            # Approval/execution plumbing is present, but no write-capable
            # production adapter is silently enabled by bootstrap.
            self.assertIsInstance(bundle.service._remediation, DisabledRemediationClient)
        finally:
            bundle.close()


if __name__ == "__main__":
    unittest.main()

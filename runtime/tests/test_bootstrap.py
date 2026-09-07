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
from log_activation import create_log_activation_record, preflight_loki, write_log_activation_record
from log_evidence import LogQueryResult
from onboarding import PreflightResult, PreflightSlot, load_telemetry_profile
from production_remediation import AllowlistedProductionRemediationClient
from telemetry import investigation_queries, recovery_queries


class FakeMetrics:
    def __init__(self, datasource_uid: str = "prom-main") -> None:
        self.datasource_uid = datasource_uid
        self.closed = False

    def instant(self, _promql: str) -> float:
        return 1.0

    def close(self) -> None:
        self.closed = True


class FakeLogs:
    def __init__(self, datasource_uid: str = "loki-main") -> None:
        self.datasource_uid = datasource_uid
        self.closed = False
        self.calls = []

    def range(self, logql: str, *, start: str, end: str, limit: int) -> LogQueryResult:
        self.calls.append((logql, start, end, limit))
        return LogQueryResult((), False, start, end)

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
            profile, datasource_uid, preflight, now_unix=1_800_000_000, ttl_seconds=3600
        )
        path = self.root / "activation.json"
        write_activation_record(path, record)
        return path

    def _log_activation(self, config: Path, datasource_uid: str = "loki-main") -> Path:
        profile = load_telemetry_profile(config)
        client = FakeLogs(datasource_uid)
        preflight = preflight_loki(client, profile)
        record = create_log_activation_record(
            profile, datasource_uid, preflight, now_unix=1_800_000_000, ttl_seconds=3600
        )
        path = self.root / "log-activation.json"
        write_log_activation_record(path, record)
        return path

    def _production_bundle(self, config: Path, activation: Path, log_activation: Path, **kwargs):
        return build_runtime(
            telemetry_config=config,
            activation_path=activation,
            log_activation_path=log_activation,
            audit_path=self.root / "audit.jsonl",
            metrics_factory=kwargs.pop("metrics_factory", FakeMetrics),
            logs_factory=kwargs.pop("logs_factory", FakeLogs),
            activation_now_unix=1_800_000_100,
            port=0,
            **kwargs,
        )

    def test_production_profile_refuses_startup_without_metric_activation(self) -> None:
        config = self._write_profile()
        metrics = FakeMetrics()
        with self.assertRaisesRegex(ValueError, "requires --activation"):
            build_runtime(
                telemetry_config=config,
                activation_path=None,
                log_activation_path=None,
                audit_path=self.root / "audit.jsonl",
                metrics_factory=lambda: metrics,
                logs_factory=FakeLogs,
                activation_now_unix=1_800_000_100,
                port=0,
            )
        self.assertTrue(metrics.closed)

    def test_production_profile_refuses_startup_without_log_activation(self) -> None:
        config = self._write_profile()
        activation = self._activation(config)
        with self.assertRaisesRegex(ValueError, "requires --log-activation"):
            build_runtime(
                telemetry_config=config,
                activation_path=activation,
                log_activation_path=None,
                audit_path=self.root / "audit.jsonl",
                metrics_factory=FakeMetrics,
                logs_factory=FakeLogs,
                activation_now_unix=1_800_000_100,
                port=0,
            )

    def test_metric_activation_is_verified_against_actual_datasource(self) -> None:
        config = self._write_profile()
        activation = self._activation(config, "prom-approved")
        log_activation = self._log_activation(config)
        metrics = FakeMetrics("prom-drifted")
        with self.assertRaisesRegex(ValueError, "datasource identity changed"):
            self._production_bundle(
                config, activation, log_activation, metrics_factory=lambda: metrics
            )
        self.assertTrue(metrics.closed)

    def test_log_activation_is_verified_against_actual_datasource(self) -> None:
        config = self._write_profile()
        activation = self._activation(config)
        log_activation = self._log_activation(config, "loki-approved")
        logs = FakeLogs("loki-drifted")
        with self.assertRaisesRegex(ValueError, "Loki datasource identity changed"):
            self._production_bundle(
                config, activation, log_activation, logs_factory=lambda: logs
            )
        self.assertTrue(logs.closed)

    def test_non_loopback_requires_process_owned_bearer_token(self) -> None:
        config = self._write_profile()
        activation = self._activation(config)
        log_activation = self._log_activation(config)
        with clean_auth_env(), self.assertRaisesRegex(ValueError, "STAGEGUARD_API_TOKEN"):
            self._production_bundle(
                config, activation, log_activation, host="0.0.0.0"
            )

    def test_loopback_demo_defaults_to_local_identity(self) -> None:
        example = Path(__file__).parents[1] / "telemetry.example.json"
        with clean_auth_env():
            bundle = build_runtime(
                telemetry_config=example,
                activation_path=None,
                log_activation_path=None,
                audit_path=self.root / "audit.jsonl",
                host="127.0.0.1",
                port=0,
                metrics_factory=FakeMetrics,
                logs_factory=FakeLogs,
            )
        try:
            self.assertTrue(bundle.identity_provider.is_development_only)
            self.assertIsNone(bundle.logs)
        finally:
            bundle.close()

    def test_production_runtime_uses_correlated_evidence_and_disabled_writes_by_default(self) -> None:
        config = self._write_profile()
        activation = self._activation(config)
        log_activation = self._log_activation(config)
        with patch.dict(
            os.environ,
            {"STAGEGUARD_API_TOKEN": "secret", "STAGEGUARD_API_SUBJECT": "ops@example"},
            clear=False,
        ):
            bundle = self._production_bundle(
                config, activation, log_activation, host="0.0.0.0"
            )
        try:
            self.assertFalse(bundle.identity_provider.is_development_only)
            self.assertIsInstance(bundle.service._remediation, DisabledRemediationClient)
            self.assertIsNotNone(bundle.logs)
            self.assertIs(bundle.service._logs, bundle.logs)
        finally:
            bundle.close()

    def test_explicit_production_remediation_requires_separate_write_settings(self) -> None:
        config = self._write_profile()
        activation = self._activation(config)
        log_activation = self._log_activation(config)
        env = {"STAGEGUARD_API_TOKEN": "api-secret", "STAGEGUARD_API_SUBJECT": "ops@example"}
        with patch.dict(os.environ, env, clear=True), self.assertRaisesRegex(
            ValueError, "STAGEGUARD_REMEDIATION_ENDPOINT"
        ):
            self._production_bundle(
                config, activation, log_activation,
                host="0.0.0.0", enable_production_remediation=True
            )

    def test_explicit_production_remediation_wires_allowlisted_https_adapter(self) -> None:
        config = self._write_profile()
        activation = self._activation(config)
        log_activation = self._log_activation(config)
        env = {
            "STAGEGUARD_API_TOKEN": "api-secret",
            "STAGEGUARD_API_SUBJECT": "ops@example",
            "STAGEGUARD_REMEDIATION_ENDPOINT": "https://writer.example/v1/recover",
            "STAGEGUARD_REMEDIATION_TOKEN": "write-secret",
        }
        with patch.dict(os.environ, env, clear=True):
            bundle = self._production_bundle(
                config, activation, log_activation,
                host="0.0.0.0", enable_production_remediation=True
            )
        try:
            self.assertIsInstance(bundle.service._remediation, AllowlistedProductionRemediationClient)
        finally:
            bundle.close()

    def test_demo_profile_refuses_production_write_opt_in(self) -> None:
        example = Path(__file__).parents[1] / "telemetry.example.json"
        with self.assertRaisesRegex(ValueError, "not permitted for the demo"):
            build_runtime(
                telemetry_config=example,
                activation_path=None,
                log_activation_path=None,
                audit_path=self.root / "audit.jsonl",
                port=0,
                metrics_factory=FakeMetrics,
                logs_factory=FakeLogs,
                enable_production_remediation=True,
            )


if __name__ == "__main__":
    unittest.main()

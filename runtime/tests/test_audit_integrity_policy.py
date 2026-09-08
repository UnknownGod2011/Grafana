from __future__ import annotations

import unittest
from unittest.mock import patch

from api import _lifecycle_view, _service_metrics, _service_readiness
from bootstrap import _parser
from cloudrun_entrypoint import build_bootstrap_argv


class ReadyResult:
    def to_dict(self):
        return {"ready": True, "checks": {"prometheus_mcp": "ok", "loki_mcp": "ok"}}


class ReadyProbe:
    def check(self):
        return ReadyResult()

    def prometheus_metrics(self):
        return ""


class PolicyService:
    _checkpoint_store = None

    def __init__(self, integrity: str, policy: str = "allow_unbound_legacy") -> None:
        self.integrity = integrity
        self._audit_integrity_policy = policy

    def audit_integrity_state(self):
        return self.integrity

    def checkpoint_state(self):
        return "synchronized"

    def status(self):
        return None


class AuditIntegrityPolicyTests(unittest.TestCase):
    def test_require_verified_blocks_every_nonverified_state(self) -> None:
        with patch("api._get_readiness_probe", return_value=ReadyProbe()):
            for state in ("disabled", "unbound_legacy", "failed"):
                with self.subTest(state=state):
                    readiness = _service_readiness(PolicyService(state, "require_verified"))
                    self.assertFalse(readiness["ready"])
                    self.assertEqual("require_verified", readiness["checks"]["audit_integrity_policy"])

            readiness = _service_readiness(PolicyService("verified", "require_verified"))
            self.assertTrue(readiness["ready"])

    def test_migration_policy_preserves_legacy_compatibility_but_not_failed_integrity(self) -> None:
        with patch("api._get_readiness_probe", return_value=ReadyProbe()):
            self.assertTrue(_service_readiness(PolicyService("unbound_legacy"))["ready"])
            self.assertFalse(_service_readiness(PolicyService("failed"))["ready"])

    def test_policy_is_exposed_without_dynamic_metric_labels(self) -> None:
        service = PolicyService("verified", "require_verified")
        with patch("api._get_readiness_probe", return_value=ReadyProbe()):
            view = _lifecycle_view(service)
            metrics = _service_metrics(service)

        self.assertEqual("require_verified", view["audit_integrity_policy"])
        self.assertIn('stageguard_audit_integrity_policy{policy="allow_unbound_legacy"} 0', metrics)
        self.assertIn('stageguard_audit_integrity_policy{policy="require_verified"} 1', metrics)
        self.assertIn("stageguard_audit_integrity_policy_satisfied 1", metrics)
        self.assertNotIn("checkpoint-head-sha", metrics)
        self.assertNotIn("provider-operation", metrics)

    def test_invalid_runtime_policy_fails_hardened(self) -> None:
        service = PolicyService("unbound_legacy", "provider-operation")
        with patch("api._get_readiness_probe", return_value=ReadyProbe()):
            readiness = _service_readiness(service)
            metrics = _service_metrics(service)
        self.assertFalse(readiness["ready"])
        self.assertEqual("require_verified", readiness["checks"]["audit_integrity_policy"])
        self.assertNotIn("provider-operation", metrics)

    def test_bootstrap_cli_has_explicit_migration_and_hardened_modes(self) -> None:
        parser = _parser()
        base = ["--telemetry-config", "telemetry.json"]
        self.assertEqual("allow_unbound_legacy", parser.parse_args(base).audit_integrity_policy)
        hardened = parser.parse_args(base + ["--audit-integrity-policy", "require_verified"])
        self.assertEqual("require_verified", hardened.audit_integrity_policy)
        with self.assertRaises(SystemExit):
            parser.parse_args(base + ["--audit-integrity-policy", "arbitrary-provider-value"])

    def test_cloud_run_gcs_defaults_to_require_verified(self) -> None:
        env = {
            "PORT": "8080",
            "STAGEGUARD_TELEMETRY_CONFIG": "/config/telemetry.json",
            "STAGEGUARD_METRIC_ACTIVATION": "/config/activation.json",
            "STAGEGUARD_LOG_ACTIVATION": "/config/log-activation.json",
            "STAGEGUARD_IAP_AUDIENCE": "/projects/1/global/backendServices/2",
            "STAGEGUARD_CHECKPOINT_BUCKET": "stageguard-state-prod",
            "STAGEGUARD_CHECKPOINT_HMAC_KEY": "k" * 32,
        }
        argv = build_bootstrap_argv(env)
        self.assertEqual("gcs", argv[argv.index("--checkpoint-backend") + 1])
        self.assertEqual("require_verified", argv[argv.index("--audit-integrity-policy") + 1])

    def test_cloud_run_without_durable_checkpoint_does_not_claim_verified_requirement(self) -> None:
        env = {
            "PORT": "8080",
            "STAGEGUARD_TELEMETRY_CONFIG": "/config/telemetry.json",
            "STAGEGUARD_METRIC_ACTIVATION": "/config/activation.json",
            "STAGEGUARD_LOG_ACTIVATION": "/config/log-activation.json",
            "STAGEGUARD_IAP_AUDIENCE": "/projects/1/global/backendServices/2",
        }
        argv = build_bootstrap_argv(env)
        self.assertEqual("none", argv[argv.index("--checkpoint-backend") + 1])
        self.assertEqual("allow_unbound_legacy", argv[argv.index("--audit-integrity-policy") + 1])


if __name__ == "__main__":
    unittest.main()

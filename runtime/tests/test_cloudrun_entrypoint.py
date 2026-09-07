from __future__ import annotations

import unittest

from cloudrun_entrypoint import build_bootstrap_argv


class CloudRunEntrypointTests(unittest.TestCase):
    def _env(self) -> dict[str, str]:
        return {
            "PORT": "8080",
            "STAGEGUARD_TELEMETRY_CONFIG": "/config/telemetry.json",
            "STAGEGUARD_METRIC_ACTIVATION": "/config/activation.json",
            "STAGEGUARD_LOG_ACTIVATION": "/config/log-activation.json",
            "STAGEGUARD_IAP_AUDIENCE": "/projects/123456/global/backendServices/987654",
        }

    def test_builds_fixed_safe_production_composition(self) -> None:
        argv = build_bootstrap_argv(self._env())
        self.assertEqual(argv[argv.index("--identity-mode") + 1], "iap")
        self.assertEqual(argv[argv.index("--audit-backend") + 1], "cloud-logging")
        self.assertEqual(argv[argv.index("--host") + 1], "0.0.0.0")
        self.assertEqual(argv[argv.index("--port") + 1], "8080")
        self.assertEqual(argv[argv.index("--checkpoint-backend") + 1], "none")
        self.assertNotIn("--enable-production-remediation", argv)

    def test_checkpoint_bucket_enables_durable_gcs_store(self) -> None:
        env = self._env()
        env["STAGEGUARD_CHECKPOINT_BUCKET"] = "stageguard-state-prod"
        env["STAGEGUARD_CHECKPOINT_OBJECT"] = "prod/current.json"
        argv = build_bootstrap_argv(env)
        self.assertEqual(argv[argv.index("--checkpoint-backend") + 1], "gcs")
        self.assertEqual(argv[argv.index("--checkpoint-object") + 1], "prod/current.json")
        self.assertNotIn("stageguard-state-prod", argv)  # bucket stays environment-owned

    def test_gemini_is_opt_in(self) -> None:
        env = self._env()
        self.assertNotIn("--enable-gemini", build_bootstrap_argv(env))
        env["STAGEGUARD_ENABLE_GEMINI"] = "true"
        self.assertIn("--enable-gemini", build_bootstrap_argv(env))

    def test_missing_required_mount_or_iap_audience_fails_closed(self) -> None:
        for name in (
            "STAGEGUARD_TELEMETRY_CONFIG",
            "STAGEGUARD_METRIC_ACTIVATION",
            "STAGEGUARD_LOG_ACTIVATION",
            "STAGEGUARD_IAP_AUDIENCE",
        ):
            with self.subTest(name=name):
                env = self._env()
                del env[name]
                with self.assertRaisesRegex(ValueError, name):
                    build_bootstrap_argv(env)

    def test_port_is_bounded(self) -> None:
        for value in ("0", "65536", "not-a-port"):
            with self.subTest(value=value):
                env = self._env()
                env["PORT"] = value
                with self.assertRaises(ValueError):
                    build_bootstrap_argv(env)


if __name__ == "__main__":
    unittest.main()

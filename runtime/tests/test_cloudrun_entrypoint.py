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
        self.assertEqual(argv[argv.index("--audit-integrity-policy") + 1], "allow_unbound_legacy")
        self.assertNotIn("--enable-production-remediation", argv)

    def test_checkpoint_bucket_requires_strong_hmac_secret_and_enables_gcs(self) -> None:
        env = self._env()
        env["STAGEGUARD_CHECKPOINT_BUCKET"] = "stageguard-state-prod"
        with self.assertRaisesRegex(ValueError, "STAGEGUARD_CHECKPOINT_HMAC_KEY"):
            build_bootstrap_argv(env)
        env["STAGEGUARD_CHECKPOINT_HMAC_KEY"] = "short"
        with self.assertRaisesRegex(ValueError, "at least 32 bytes"):
            build_bootstrap_argv(env)
        env["STAGEGUARD_CHECKPOINT_HMAC_KEY"] = "k" * 32
        env["STAGEGUARD_CHECKPOINT_OBJECT"] = "prod/current.json"
        argv = build_bootstrap_argv(env)
        self.assertEqual(argv[argv.index("--checkpoint-backend") + 1], "gcs")
        self.assertEqual(argv[argv.index("--checkpoint-object") + 1], "prod/current.json")
        self.assertEqual(argv[argv.index("--audit-integrity-policy") + 1], "require_verified")
        self.assertNotIn("stageguard-state-prod", argv)
        self.assertNotIn("k" * 32, argv)

    def test_checkpoint_object_defaults_to_bounded_stageguard_path(self) -> None:
        env = self._env()
        env["STAGEGUARD_CHECKPOINT_BUCKET"] = "stageguard-state-prod"
        env["STAGEGUARD_CHECKPOINT_HMAC_KEY"] = "k" * 32
        argv = build_bootstrap_argv(env)
        self.assertEqual(
            argv[argv.index("--checkpoint-object") + 1],
            "stageguard/incident-checkpoint.json",
        )

    def test_invalid_checkpoint_bucket_fails_closed(self) -> None:
        for value in (
            "ab",
            "StageGuard-State",
            "192.168.0.1",
            "stageguard..state",
            "goog-stageguard-state",
            "stageguard_google_state",
            "-stageguard-state",
        ):
            with self.subTest(value=value):
                env = self._env()
                env["STAGEGUARD_CHECKPOINT_BUCKET"] = value
                env["STAGEGUARD_CHECKPOINT_HMAC_KEY"] = "k" * 32
                with self.assertRaisesRegex(ValueError, "STAGEGUARD_CHECKPOINT_BUCKET"):
                    build_bootstrap_argv(env)

    def test_invalid_checkpoint_object_fails_closed(self) -> None:
        for value in (
            "/prod/current.json",
            "prod//current.json",
            "prod/../current.json",
            "prod/./current.json",
            "prod\\current.json",
            "prod/current.json,other",
            "prod/current.json ",
            "prod/\x00current.json",
        ):
            with self.subTest(value=value):
                env = self._env()
                env["STAGEGUARD_CHECKPOINT_BUCKET"] = "stageguard-state-prod"
                env["STAGEGUARD_CHECKPOINT_HMAC_KEY"] = "k" * 32
                env["STAGEGUARD_CHECKPOINT_OBJECT"] = value
                with self.assertRaisesRegex(ValueError, "STAGEGUARD_CHECKPOINT_OBJECT"):
                    build_bootstrap_argv(env)

    def test_orphan_checkpoint_configuration_fails_closed(self) -> None:
        for name, value in (
            ("STAGEGUARD_CHECKPOINT_OBJECT", "prod/current.json"),
            ("STAGEGUARD_CHECKPOINT_HMAC_KEY", "k" * 32),
        ):
            with self.subTest(name=name):
                env = self._env()
                env[name] = value
                with self.assertRaisesRegex(ValueError, name):
                    build_bootstrap_argv(env)

    def test_gemini_is_opt_in(self) -> None:
        env = self._env()
        self.assertNotIn("--enable-gemini", build_bootstrap_argv(env))
        env["STAGEGUARD_ENABLE_GEMINI"] = "true"
        self.assertIn("--enable-gemini", build_bootstrap_argv(env))

    def test_gemini_boolean_aliases_are_explicit(self) -> None:
        for value in ("1", "true", "TRUE", "yes", "on", "  true  "):
            with self.subTest(value=value):
                env = self._env()
                env["STAGEGUARD_ENABLE_GEMINI"] = value
                self.assertIn("--enable-gemini", build_bootstrap_argv(env))
        for value in ("0", "false", "FALSE", "no", "off", "", "   "):
            with self.subTest(value=value):
                env = self._env()
                env["STAGEGUARD_ENABLE_GEMINI"] = value
                self.assertNotIn("--enable-gemini", build_bootstrap_argv(env))

    def test_invalid_gemini_flag_fails_closed(self) -> None:
        for value in ("treu", "enabled", "2", "maybe"):
            with self.subTest(value=value):
                env = self._env()
                env["STAGEGUARD_ENABLE_GEMINI"] = value
                with self.assertRaisesRegex(ValueError, "STAGEGUARD_ENABLE_GEMINI"):
                    build_bootstrap_argv(env)

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

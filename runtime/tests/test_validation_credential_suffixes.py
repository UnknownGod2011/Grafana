from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "scripts" / "run_stageguard_validation.py"
_spec = importlib.util.spec_from_file_location("stageguard_validation_runner_credential_suffixes", RUNNER)
assert _spec is not None and _spec.loader is not None
runner = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = runner
_spec.loader.exec_module(runner)


class ValidationCredentialSuffixTests(unittest.TestCase):
    def test_generic_credential_suffixes_are_case_insensitive(self):
        sensitive = (
            "SERVICE_AUTH_TOKEN",
            "service_bearer_token",
            "MEDIA_CREDENTIAL",
            "media_credentials",
            "vendor_client_secret",
        )
        for name in sensitive:
            with self.subTest(name=name):
                self.assertTrue(runner._is_sensitive_env_name(name))

    def test_generic_credentials_are_removed_without_overmatching_configuration(self):
        source = {
            "PATH": "/usr/bin",
            "SERVICE_AUTH_TOKEN": "secret",
            "PLAYER_BEARER_TOKEN": "secret",
            "MEDIA_CREDENTIAL": "secret",
            "MEDIA_CREDENTIALS": "secret",
            "MEDIA_CREDENTIAL_MODE": "workload-identity",
            "STAGEGUARD_REGION": "us-central1",
        }
        sanitized = runner._validation_env(source)
        for name in (
            "SERVICE_AUTH_TOKEN",
            "PLAYER_BEARER_TOKEN",
            "MEDIA_CREDENTIAL",
            "MEDIA_CREDENTIALS",
        ):
            self.assertNotIn(name, sanitized)
        self.assertEqual(sanitized["MEDIA_CREDENTIAL_MODE"], "workload-identity")
        self.assertEqual(sanitized["STAGEGUARD_REGION"], "us-central1")


if __name__ == "__main__":
    unittest.main()

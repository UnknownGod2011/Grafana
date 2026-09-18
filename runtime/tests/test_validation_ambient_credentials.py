from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "scripts" / "run_stageguard_validation.py"


def _load_runner():
    spec = importlib.util.spec_from_file_location("stageguard_validation_ambient_credentials", RUNNER)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load validation runner: {RUNNER}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class ValidationAmbientCredentialIsolationTests(unittest.TestCase):
    """Dependency-light validation must not accidentally inherit developer/CI credentials."""

    @classmethod
    def setUpClass(cls):
        cls.runner = _load_runner()

    def test_adjacent_provider_credentials_are_scrubbed_case_insensitively(self):
        names = (
            "AWS_ACCESS_KEY_ID",
            "aws_session_token",
            "AZURE_CLIENT_SECRET",
            "Anthropic_Api_Key",
            "OPENAI_API_KEY",
            "GITHUB_TOKEN",
            "gh_token",
            "HF_TOKEN",
            "HUGGINGFACE_TOKEN",
        )
        source = {name: "must-not-leak" for name in names}
        source.update({"PATH": "/usr/bin", "STAGEGUARD_TEST_MODE": "safe"})

        sanitized = self.runner._validation_env(source)

        for name in names:
            with self.subTest(name=name):
                self.assertNotIn(name, sanitized)
                self.assertTrue(self.runner._is_sensitive_env_name(name))
        self.assertEqual(sanitized["STAGEGUARD_TEST_MODE"], "safe")

    def test_generic_secret_suffixes_are_scrubbed(self):
        names = (
            "VENDOR_ACCESS_KEY",
            "SERVICE_PRIVATE_KEY",
            "OIDC_CLIENT_SECRET",
        )
        sanitized = self.runner._validation_env({**{name: "secret" for name in names}, "SAFE_FLAG": "1"})
        for name in names:
            with self.subTest(name=name):
                self.assertNotIn(name, sanitized)
        self.assertEqual(sanitized["SAFE_FLAG"], "1")

    def test_noncredential_provider_configuration_is_not_over_scrubbed(self):
        source = {
            "GOOGLE_CLOUD_PROJECT": "stageguard-test",
            "ORDINARY_SETTING": "safe",
        }
        sanitized = self.runner._validation_env(source)
        self.assertEqual(sanitized["GOOGLE_CLOUD_PROJECT"], "stageguard-test")
        self.assertEqual(sanitized["ORDINARY_SETTING"], "safe")


if __name__ == "__main__":
    unittest.main()

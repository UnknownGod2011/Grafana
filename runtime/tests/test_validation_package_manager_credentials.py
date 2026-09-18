from __future__ import annotations
import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "scripts" / "run_stageguard_validation.py"
_spec = importlib.util.spec_from_file_location("stageguard_validation_package_manager_runner", RUNNER)
assert _spec is not None and _spec.loader is not None
runner = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = runner
_spec.loader.exec_module(runner)


class ValidationPackageManagerCredentialIsolationTests(unittest.TestCase):
    def test_registry_and_client_config_channels_are_removed(self):
        source = {
            "PATH": "/usr/bin",
            "PIP_INDEX_URL": "https://user:secret@packages.example/simple",
            "pip_extra_index_url": "https://token@private.example/simple",
            "PIP_CONFIG_FILE": "/real/pip.conf",
            "NPM_CONFIG_USERCONFIG": "/real/.npmrc",
            "YARN_RC_FILENAME": "/real/.yarnrc",
            "CURL_HOME": "/real/curl-home",
            "WGETRC": "/real/.wgetrc",
            "STAGEGUARD_REGION": "us-central1",
        }
        sanitized = runner._validation_env(source)
        for name in (
            "PIP_INDEX_URL", "pip_extra_index_url", "PIP_CONFIG_FILE",
            "NPM_CONFIG_USERCONFIG", "YARN_RC_FILENAME", "CURL_HOME", "WGETRC",
        ):
            self.assertNotIn(name, sanitized)
        self.assertEqual(sanitized["STAGEGUARD_REGION"], "us-central1")
        self.assertFalse(any("packages.example" in value or "private.example" in value for value in sanitized.values()))

    def test_package_manager_matching_is_case_insensitive(self):
        for name in ("pip_index_url", "Pip_Config_File", "npm_config_userconfig", "yarn_rc_filename", "curl_home", "wgetrc"):
            with self.subTest(name=name):
                self.assertTrue(runner._is_sensitive_env_name(name))

    def test_pip_is_forced_non_interactive(self):
        sanitized = runner._validation_env({"PIP_NO_INPUT": "0", "SAFE": "value"})
        self.assertEqual(sanitized["PIP_NO_INPUT"], "1")
        self.assertEqual(sanitized["SAFE"], "value")


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "scripts" / "run_stageguard_validation.py"
_spec = importlib.util.spec_from_file_location("stageguard_validation_home_isolation", RUNNER)
assert _spec is not None and _spec.loader is not None
runner = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = runner
_spec.loader.exec_module(runner)


class ValidationHomeIsolationTests(unittest.TestCase):
    def test_helper_without_isolated_home_does_not_inherit_credential_discovery_homes(self):
        source = {
            "PATH": "/usr/bin",
            "HOME": "/real/home",
            "USERPROFILE": "C:/Users/real",
            "CLOUDSDK_CONFIG": "/real/gcloud",
            "XDG_CONFIG_HOME": "/real/xdg-config",
            "XDG_DATA_HOME": "/real/xdg-data",
            "APPDATA": "C:/Users/real/AppData/Roaming",
            "LOCALAPPDATA": "C:/Users/real/AppData/Local",
            "ORDINARY_SETTING": "safe",
        }
        sanitized = runner._validation_env(source)
        for name in (
            "HOME",
            "USERPROFILE",
            "CLOUDSDK_CONFIG",
            "XDG_CONFIG_HOME",
            "XDG_DATA_HOME",
            "APPDATA",
            "LOCALAPPDATA",
        ):
            with self.subTest(name=name):
                self.assertNotIn(name, sanitized)
        self.assertEqual(sanitized["ORDINARY_SETTING"], "safe")
        self.assertFalse(any("/real/" in value or "C:/Users/real" in value for value in sanitized.values()))

    def test_home_names_are_sensitive_case_insensitively(self):
        for name in ("HOME", "home", "UserProfile", "USERPROFILE"):
            with self.subTest(name=name):
                self.assertTrue(runner._is_sensitive_env_name(name))

    def test_isolated_home_reinstalls_only_ephemeral_discovery_roots(self):
        source = {
            "HOME": "/real/home",
            "USERPROFILE": "C:/Users/real",
            "CLOUDSDK_CONFIG": "/real/gcloud",
            "ORDINARY_SETTING": "safe",
        }
        isolated = "/tmp/stageguard-validation-home"
        sanitized = runner._validation_env(source, isolated_home=isolated)
        self.assertEqual(sanitized["HOME"], isolated)
        self.assertEqual(sanitized["USERPROFILE"], isolated)
        self.assertEqual(sanitized["CLOUDSDK_CONFIG"], str(Path(isolated) / ".config" / "gcloud"))
        self.assertEqual(sanitized["ORDINARY_SETTING"], "safe")
        self.assertNotIn("/real/home", sanitized.values())
        self.assertNotIn("C:/Users/real", sanitized.values())
        self.assertNotIn("/real/gcloud", sanitized.values())


if __name__ == "__main__":
    unittest.main()

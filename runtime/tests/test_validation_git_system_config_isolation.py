from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "scripts" / "run_stageguard_validation.py"
_spec = importlib.util.spec_from_file_location("stageguard_validation_git_system_config", RUNNER)
assert _spec is not None and _spec.loader is not None
runner = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = runner
_spec.loader.exec_module(runner)


class ValidationGitSystemConfigIsolationTests(unittest.TestCase):
    def test_host_git_config_controls_are_replaced_by_trusted_no_system_override(self):
        source = {
            "PATH": "/usr/bin",
            "GIT_CONFIG_NOSYSTEM": "0",
            "git_config_system": "/host/attacker.gitconfig",
            "GIT_CONFIG_GLOBAL": "/host/user.gitconfig",
            "ORDINARY_SETTING": "safe",
        }
        sanitized = runner._validation_env(source)

        self.assertEqual(sanitized["GIT_CONFIG_NOSYSTEM"], "1")
        self.assertNotIn("git_config_system", sanitized)
        self.assertNotIn("GIT_CONFIG_GLOBAL", sanitized)
        self.assertNotIn("/host/attacker.gitconfig", sanitized.values())
        self.assertNotIn("/host/user.gitconfig", sanitized.values())
        self.assertEqual(sanitized["GIT_TERMINAL_PROMPT"], "0")
        self.assertEqual(sanitized["GIT_PAGER"], "cat")
        self.assertEqual(sanitized["PATH"], "/usr/bin")
        self.assertEqual(sanitized["ORDINARY_SETTING"], "safe")

    def test_git_config_no_system_is_sensitive_case_insensitively(self):
        for name in ("GIT_CONFIG_NOSYSTEM", "git_config_nosystem", "Git_Config_NoSystem"):
            with self.subTest(name=name):
                self.assertTrue(runner._is_sensitive_env_name(name))


if __name__ == "__main__":
    unittest.main()

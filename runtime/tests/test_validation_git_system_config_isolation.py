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
    def test_host_git_state_is_replaced_by_trusted_overrides(self):
        source = {
            "PATH": "/usr/bin",
            "GIT_CONFIG_NOSYSTEM": "0",
            "git_config_system": "/host/attacker.gitconfig",
            "GIT_CONFIG_GLOBAL": "/host/user.gitconfig",
            "GIT_ATTR_NOSYSTEM": "0",
            "git_attr_host_control": "/host/attributes",
            "GIT_DIR": "/host/attacker.git",
            "git_work_tree": "/host/worktree",
            "Git_Index_File": "/host/index",
            "GIT_OBJECT_DIRECTORY": "/host/objects",
            "GIT_ALTERNATE_OBJECT_DIRECTORIES": "/host/alternate-objects",
            "GIT_CEILING_DIRECTORIES": "/host",
            "GIT_DISCOVERY_ACROSS_FILESYSTEM": "1",
            "GIT_NAMESPACE": "attacker",
            "ORDINARY_SETTING": "safe",
        }
        sanitized = runner._validation_env(source)

        self.assertEqual(sanitized["GIT_CONFIG_NOSYSTEM"], "1")
        self.assertEqual(sanitized["GIT_ATTR_NOSYSTEM"], "1")
        for hostile_name in (
            "git_config_system",
            "GIT_CONFIG_GLOBAL",
            "git_attr_host_control",
            "GIT_DIR",
            "git_work_tree",
            "Git_Index_File",
            "GIT_OBJECT_DIRECTORY",
            "GIT_ALTERNATE_OBJECT_DIRECTORIES",
            "GIT_CEILING_DIRECTORIES",
            "GIT_DISCOVERY_ACROSS_FILESYSTEM",
            "GIT_NAMESPACE",
        ):
            self.assertNotIn(hostile_name, sanitized)
        for hostile_value in (
            "/host/attacker.gitconfig",
            "/host/user.gitconfig",
            "/host/attributes",
            "/host/attacker.git",
            "/host/worktree",
            "/host/index",
            "/host/objects",
            "/host/alternate-objects",
            "/host",
            "attacker",
        ):
            self.assertNotIn(hostile_value, sanitized.values())
        self.assertEqual(sanitized["GIT_TERMINAL_PROMPT"], "0")
        self.assertEqual(sanitized["GIT_PAGER"], "cat")
        self.assertEqual(sanitized["PATH"], "/usr/bin")
        self.assertEqual(sanitized["ORDINARY_SETTING"], "safe")

    def test_all_git_environment_controls_are_sensitive_case_insensitively(self):
        for name in (
            "GIT_CONFIG_NOSYSTEM",
            "git_config_nosystem",
            "Git_Config_NoSystem",
            "GIT_ATTR_NOSYSTEM",
            "git_attr_nosystem",
            "Git_Attr_NoSystem",
            "GIT_DIR",
            "git_work_tree",
            "Git_Index_File",
            "GIT_OBJECT_DIRECTORY",
            "git_alternate_object_directories",
            "Git_Ceiling_Directories",
            "GIT_DISCOVERY_ACROSS_FILESYSTEM",
            "git_namespace",
        ):
            with self.subTest(name=name):
                self.assertTrue(runner._is_sensitive_env_name(name))


if __name__ == "__main__":
    unittest.main()

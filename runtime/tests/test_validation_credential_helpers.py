from __future__ import annotations
import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "scripts" / "run_stageguard_validation.py"
_spec = importlib.util.spec_from_file_location("stageguard_validation_credential_helpers", RUNNER)
assert _spec is not None and _spec.loader is not None
runner = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = runner
_spec.loader.exec_module(runner)


class ValidationCredentialHelperIsolationTests(unittest.TestCase):
    def test_credential_helper_and_external_config_channels_are_removed(self):
        source = {
            "PATH": "/usr/bin",
            "SSH_AUTH_SOCK": "/run/user/1000/ssh-agent.sock",
            "SSH_AGENT_PID": "1234",
            "GIT_ASKPASS": "/tmp/credential-helper",
            "SSH_ASKPASS": "/tmp/ssh-helper",
            "GIT_SSH": "/tmp/custom-ssh",
            "GIT_SSH_COMMAND": "ssh -i /tmp/private-key",
            "NETRC": "/home/user/.netrc",
            "DOCKER_CONFIG": "/home/user/.docker",
            "KUBECONFIG": "/home/user/.kube/config",
            "XDG_CONFIG_HOME": "/home/user/.config",
            "XDG_DATA_HOME": "/home/user/.local/share",
            "APPDATA": "C:/Users/user/AppData/Roaming",
            "LOCALAPPDATA": "C:/Users/user/AppData/Local",
            "ORDINARY_SETTING": "safe",
        }
        sanitized = runner._validation_env(source)
        for name in set(source) - {"PATH", "ORDINARY_SETTING"}:
            with self.subTest(name=name):
                self.assertNotIn(name, sanitized)
        self.assertEqual(sanitized["ORDINARY_SETTING"], "safe")

    def test_isolated_home_rehomes_cross_platform_config_roots(self):
        source = {
            "HOME": "/home/real-user",
            "USERPROFILE": "C:/Users/real-user",
            "XDG_CONFIG_HOME": "/home/real-user/.config",
            "XDG_DATA_HOME": "/home/real-user/.local/share",
            "APPDATA": "C:/Users/real-user/AppData/Roaming",
            "LOCALAPPDATA": "C:/Users/real-user/AppData/Local",
        }
        isolated = "/tmp/stageguard-validation-test"
        sanitized = runner._validation_env(source, isolated_home=isolated)
        self.assertEqual(sanitized["HOME"], isolated)
        self.assertEqual(sanitized["USERPROFILE"], isolated)
        self.assertEqual(sanitized["XDG_CONFIG_HOME"], str(Path(isolated) / ".config"))
        self.assertEqual(sanitized["XDG_DATA_HOME"], str(Path(isolated) / ".local" / "share"))
        self.assertEqual(sanitized["APPDATA"], str(Path(isolated) / "AppData" / "Roaming"))
        self.assertEqual(sanitized["LOCALAPPDATA"], str(Path(isolated) / "AppData" / "Local"))
        self.assertEqual(sanitized["CLOUDSDK_CONFIG"], str(Path(isolated) / ".config" / "gcloud"))

    def test_git_cannot_fall_back_to_interactive_terminal_prompt(self):
        sanitized = runner._validation_env({"PATH": "/usr/bin", "GIT_TERMINAL_PROMPT": "1"})
        self.assertEqual(sanitized["GIT_TERMINAL_PROMPT"], "0")

    def test_matching_is_case_insensitive_for_helper_channels(self):
        for name in ("ssh_auth_sock", "Git_AskPass", "netrc", "Docker_Config", "KubeConfig", "xdg_config_home", "AppData", "localappdata"):
            with self.subTest(name=name):
                self.assertTrue(runner._is_sensitive_env_name(name))


if __name__ == "__main__":
    unittest.main()

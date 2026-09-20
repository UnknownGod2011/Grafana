from __future__ import annotations

import importlib.util
import sys
import tempfile
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
        source = {"PATH": "/usr/bin", "HOME": "/real/home", "USERPROFILE": "C:/Users/real", "CLOUDSDK_CONFIG": "/real/gcloud", "XDG_CONFIG_HOME": "/real/xdg-config", "XDG_DATA_HOME": "/real/xdg-data", "APPDATA": "C:/Users/real/AppData/Roaming", "LOCALAPPDATA": "C:/Users/real/AppData/Local", "ORDINARY_SETTING": "safe"}
        sanitized = runner._validation_env(source)
        for name in ("HOME", "USERPROFILE", "CLOUDSDK_CONFIG", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "APPDATA", "LOCALAPPDATA"):
            with self.subTest(name=name): self.assertNotIn(name, sanitized)
        self.assertEqual(sanitized["ORDINARY_SETTING"], "safe")
        self.assertFalse(any("/real/" in value or "C:/Users/real" in value for value in sanitized.values()))

    def test_home_names_are_sensitive_case_insensitively(self):
        for name in ("HOME", "home", "UserProfile", "USERPROFILE"):
            with self.subTest(name=name): self.assertTrue(runner._is_sensitive_env_name(name))

    def test_isolated_home_reinstalls_only_ephemeral_discovery_roots(self):
        source = {"HOME": "/real/home", "USERPROFILE": "C:/Users/real", "CLOUDSDK_CONFIG": "/real/gcloud", "ORDINARY_SETTING": "safe"}
        with tempfile.TemporaryDirectory() as isolated:
            sanitized = runner._validation_env(source, isolated_home=isolated)
            self.assertEqual(sanitized["HOME"], isolated); self.assertEqual(sanitized["USERPROFILE"], isolated)
            self.assertEqual(sanitized["CLOUDSDK_CONFIG"], str(Path(isolated) / ".config" / "gcloud")); self.assertEqual(sanitized["ORDINARY_SETTING"], "safe")
            self.assertNotIn("/real/home", sanitized.values()); self.assertNotIn("C:/Users/real", sanitized.values()); self.assertNotIn("/real/gcloud", sanitized.values())

    def test_host_temporary_directories_are_removed_and_replaced_inside_isolated_home(self):
        source = {"TMPDIR": "/host/tmpdir", "TMP": "C:/host/tmp", "TEMP": "C:/host/temp", "ORDINARY_SETTING": "safe"}
        sanitized = runner._validation_env(source)
        for name in ("TMPDIR", "TMP", "TEMP"):
            with self.subTest(name=name): self.assertNotIn(name, sanitized)
        with tempfile.TemporaryDirectory() as isolated:
            sanitized = runner._validation_env(source, isolated_home=isolated)
            expected = str(Path(isolated) / "tmp")
            self.assertEqual(sanitized["TMPDIR"], expected); self.assertEqual(sanitized["TMP"], expected); self.assertEqual(sanitized["TEMP"], expected)
            self.assertTrue(Path(expected).is_dir()); self.assertEqual(sanitized["ORDINARY_SETTING"], "safe")
            self.assertFalse(any(value in sanitized.values() for value in ("/host/tmpdir", "C:/host/tmp", "C:/host/temp")))

    def test_temporary_directory_names_are_sensitive_case_insensitively(self):
        for name in ("TMPDIR", "tmpdir", "Tmp", "TEMP", "temp"):
            with self.subTest(name=name): self.assertTrue(runner._is_sensitive_env_name(name))

    def test_python_startup_and_host_path_controls_are_removed_case_insensitively(self):
        names = ("PYTHONWARNINGS", "PYTHONUSERBASE", "PYTHONPYCACHEPREFIX", "PYTHONEXECUTABLE")
        for canonical in names:
            for name in (canonical, canonical.lower(), canonical.title()):
                with self.subTest(name=name):
                    source = {"PATH": "/usr/bin", name: "/host/untrusted-python-control", "ORDINARY_SETTING": "safe"}
                    sanitized = runner._validation_env(source)
                    self.assertTrue(runner._is_sensitive_env_name(name)); self.assertNotIn(name, sanitized)
                    self.assertNotIn("/host/untrusted-python-control", sanitized.values()); self.assertEqual(sanitized["ORDINARY_SETTING"], "safe")

    def test_git_config_environment_injection_is_removed(self):
        source = {"PATH": "/usr/bin", "GIT_CONFIG_GLOBAL": "/real/home/.gitconfig", "GIT_CONFIG_SYSTEM": "/etc/host-gitconfig", "GIT_CONFIG_COUNT": "2", "GIT_CONFIG_KEY_0": "credential.helper", "GIT_CONFIG_VALUE_0": "!credential-helper-with-host-access", "git_config_key_1": "http.https://example.invalid/.extraHeader", "git_config_value_1": "Authorization: Bearer secret", "ORDINARY_SETTING": "safe"}
        sanitized = runner._validation_env(source)
        for name in set(source) - {"PATH", "ORDINARY_SETTING"}:
            with self.subTest(name=name): self.assertNotIn(name, sanitized)
        self.assertEqual(sanitized["ORDINARY_SETTING"], "safe"); self.assertFalse(any("credential-helper" in value or "Bearer secret" in value for value in sanitized.values()))

    def test_git_config_prefix_is_sensitive_case_insensitively(self):
        for name in ("GIT_CONFIG_GLOBAL", "git_config_system", "Git_Config_Count", "git_config_key_0", "GIT_CONFIG_VALUE_0"):
            with self.subTest(name=name): self.assertTrue(runner._is_sensitive_env_name(name))

    def test_pager_editor_and_less_hooks_are_sanitized_noninteractively(self):
        source = {"PATH": "/usr/bin", "GIT_PAGER": "/host/evil-git-pager", "pager": "/host/evil-pager", "ManPager": "/host/evil-manpager", "SYSTEMD_PAGER": "/host/evil-systemd-pager", "EDITOR": "/host/evil-editor", "visual": "/host/evil-visual", "LESSOPEN": "|/host/evil-less %s", "lessclose": "/host/evil-less-close %s", "ORDINARY_SETTING": "safe"}
        sanitized = runner._validation_env(source)
        for name in source:
            if name in {"PATH", "ORDINARY_SETTING"}: continue
            with self.subTest(name=name): self.assertTrue(runner._is_sensitive_env_name(name))
        for value in sanitized.values(): self.assertNotIn("/host/evil", value)
        self.assertEqual(sanitized["GIT_PAGER"], "cat"); self.assertEqual(sanitized["PAGER"], "cat"); self.assertEqual(sanitized["SYSTEMD_PAGER"], "cat")
        self.assertNotIn("EDITOR", sanitized); self.assertNotIn("visual", sanitized); self.assertNotIn("LESSOPEN", sanitized); self.assertNotIn("lessclose", sanitized)
        self.assertEqual(sanitized["ORDINARY_SETTING"], "safe")

    def test_tls_session_key_logging_is_removed_case_insensitively(self):
        for name in ("SSLKEYLOGFILE", "sslkeylogfile", "SslKeyLogFile"):
            with self.subTest(name=name):
                sanitized = runner._validation_env({"PATH": "/usr/bin", name: "/real/home/tls-secrets.log", "ORDINARY_SETTING": "safe"})
                self.assertNotIn(name, sanitized); self.assertTrue(runner._is_sensitive_env_name(name)); self.assertNotIn("/real/home/tls-secrets.log", sanitized.values()); self.assertEqual(sanitized["ORDINARY_SETTING"], "safe")

    def test_tls_trust_override_environment_is_removed_case_insensitively(self):
        for canonical in ("SSL_CERT_FILE", "SSL_CERT_DIR", "REQUESTS_CA_BUNDLE", "CURL_CA_BUNDLE"):
            for name in (canonical, canonical.lower(), canonical.title()):
                with self.subTest(name=name):
                    sanitized = runner._validation_env({"PATH": "/usr/bin", name: "/host/attacker-controlled-ca.pem", "ORDINARY_SETTING": "safe"})
                    self.assertTrue(runner._is_sensitive_env_name(name)); self.assertNotIn(name, sanitized); self.assertNotIn("/host/attacker-controlled-ca.pem", sanitized.values()); self.assertEqual(sanitized["ORDINARY_SETTING"], "safe")

    def test_dynamic_loader_injection_is_removed_case_insensitively(self):
        names = ("LD_PRELOAD", "LD_LIBRARY_PATH", "DYLD_INSERT_LIBRARIES", "DYLD_LIBRARY_PATH", "DYLD_FRAMEWORK_PATH")
        for canonical in names:
            for name in (canonical, canonical.lower(), canonical.title()):
                with self.subTest(name=name):
                    source = {"PATH": "/usr/bin", name: "/host/untrusted-loader-payload", "ORDINARY_SETTING": "safe"}; sanitized = runner._validation_env(source)
                    self.assertTrue(runner._is_sensitive_env_name(name)); self.assertNotIn(name, sanitized); self.assertNotIn("/host/untrusted-loader-payload", sanitized.values()); self.assertEqual(sanitized["ORDINARY_SETTING"], "safe")

    def test_shell_startup_injection_is_removed_case_insensitively(self):
        for canonical in ("BASH_ENV", "ENV", "ZDOTDIR"):
            for name in (canonical, canonical.lower(), canonical.title()):
                with self.subTest(name=name):
                    source = {"PATH": "/usr/bin", name: "/host/untrusted-shell-startup", "ORDINARY_SETTING": "safe"}; sanitized = runner._validation_env(source)
                    self.assertTrue(runner._is_sensitive_env_name(name)); self.assertNotIn(name, sanitized); self.assertNotIn("/host/untrusted-shell-startup", sanitized.values()); self.assertEqual(sanitized["ORDINARY_SETTING"], "safe")

    def test_bash_exported_functions_and_behavior_controls_are_removed_case_insensitively(self):
        source = {"PATH": "/usr/bin", "BASH_FUNC_git%%": "() { echo injected; }", "bash_func_curl%%": "() { echo injected; }", "BASHOPTS": "sourcepath", "shellopts": "xtrace", "CdPaTh": "/host/untrusted-cdpath", "ORDINARY_SETTING": "safe"}
        sanitized = runner._validation_env(source)
        for name in set(source) - {"PATH", "ORDINARY_SETTING"}:
            with self.subTest(name=name):
                self.assertTrue(runner._is_sensitive_env_name(name)); self.assertNotIn(name, sanitized)
        self.assertFalse(any("injected" in value or "/host/untrusted-cdpath" in value for value in sanitized.values()))
        self.assertEqual(sanitized["PATH"], "/usr/bin"); self.assertEqual(sanitized["ORDINARY_SETTING"], "safe")

    def test_language_runtime_injection_is_removed_case_insensitively(self):
        names = ("NODE_OPTIONS", "NODE_PATH", "RUBYOPT", "RUBYLIB", "PERL5OPT", "PERL5LIB", "JAVA_TOOL_OPTIONS", "JDK_JAVA_OPTIONS", "CLASSPATH")
        for canonical in names:
            for name in (canonical, canonical.lower(), canonical.title()):
                with self.subTest(name=name):
                    source = {"PATH": "/usr/bin", name: "/host/untrusted-runtime-payload", "ORDINARY_SETTING": "safe"}; sanitized = runner._validation_env(source)
                    self.assertTrue(runner._is_sensitive_env_name(name)); self.assertNotIn(name, sanitized); self.assertNotIn("/host/untrusted-runtime-payload", sanitized.values()); self.assertEqual(sanitized["ORDINARY_SETTING"], "safe")

    def test_jvm_build_tool_injection_is_removed_case_insensitively(self):
        names = ("MAVEN_OPTS", "MAVEN_ARGS", "MAVEN_USER_HOME", "GRADLE_OPTS", "GRADLE_USER_HOME")
        for canonical in names:
            for name in (canonical, canonical.lower(), canonical.title()):
                with self.subTest(name=name):
                    source = {"PATH": "/usr/bin", name: "/host/untrusted-jvm-build-tool-payload", "ORDINARY_SETTING": "safe"}; sanitized = runner._validation_env(source)
                    self.assertTrue(runner._is_sensitive_env_name(name)); self.assertNotIn(name, sanitized); self.assertNotIn("/host/untrusted-jvm-build-tool-payload", sanitized.values()); self.assertEqual(sanitized["ORDINARY_SETTING"], "safe")

    def test_dotnet_runtime_injection_is_removed_case_insensitively(self):
        names = ("DOTNET_STARTUP_HOOKS", "DOTNET_ADDITIONAL_DEPS", "DOTNET_SHARED_STORE", "CORECLR_PROFILER", "CORECLR_PROFILER_PATH", "CORECLR_ENABLE_PROFILING")
        for canonical in names:
            for name in (canonical, canonical.lower(), canonical.title()):
                with self.subTest(name=name):
                    source = {"PATH": "/usr/bin", name: "/host/untrusted-dotnet-payload", "ORDINARY_SETTING": "safe"}; sanitized = runner._validation_env(source)
                    self.assertTrue(runner._is_sensitive_env_name(name)); self.assertNotIn(name, sanitized); self.assertNotIn("/host/untrusted-dotnet-payload", sanitized.values()); self.assertEqual(sanitized["ORDINARY_SETTING"], "safe")

    def test_go_and_rust_toolchain_injection_is_removed_case_insensitively(self):
        names = ("GOENV", "GOFLAGS", "GOTOOLCHAIN", "GOWORK", "CARGO_HOME", "RUSTC_WRAPPER", "RUSTC_WORKSPACE_WRAPPER", "RUSTFLAGS", "RUSTDOCFLAGS")
        for canonical in names:
            for name in (canonical, canonical.lower(), canonical.title()):
                with self.subTest(name=name):
                    source = {"PATH": "/usr/bin", name: "/host/untrusted-toolchain-payload", "ORDINARY_SETTING": "safe"}; sanitized = runner._validation_env(source)
                    self.assertTrue(runner._is_sensitive_env_name(name)); self.assertNotIn(name, sanitized); self.assertNotIn("/host/untrusted-toolchain-payload", sanitized.values()); self.assertEqual(sanitized["ORDINARY_SETTING"], "safe")

    def test_make_environment_injection_is_removed_case_insensitively(self):
        names = ("MAKEFLAGS", "MFLAGS", "MAKEFILES")
        for canonical in names:
            for name in (canonical, canonical.lower(), canonical.title()):
                with self.subTest(name=name):
                    source = {"PATH": "/usr/bin", name: "/host/untrusted-make-control", "ORDINARY_SETTING": "safe"}
                    sanitized = runner._validation_env(source)
                    self.assertTrue(runner._is_sensitive_env_name(name)); self.assertNotIn(name, sanitized)
                    self.assertNotIn("/host/untrusted-make-control", sanitized.values()); self.assertEqual(sanitized["ORDINARY_SETTING"], "safe")


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DOCTOR = ROOT / "scripts" / "stageguard_doctor.py"
CONFIG = ROOT / "runtime" / "telemetry.example.json"


class StageGuardDoctorCliTests(unittest.TestCase):
    def _run(
        self,
        *,
        grafana_url: str | None = "https://example.grafana.net",
        token_file: Path | None = None,
        mcp_command: str | None = None,
        extra_env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        for name in (
            "GRAFANA_URL",
            "GRAFANA_SERVICE_ACCOUNT_TOKEN_FILE",
            "STAGEGUARD_MCP_COMMAND",
            "STAGEGUARD_METRIC_ACTIVATION",
            "STAGEGUARD_LOG_ACTIVATION",
        ):
            env.pop(name, None)

        if grafana_url is not None:
            env["GRAFANA_URL"] = grafana_url
        if token_file is not None:
            env["GRAFANA_SERVICE_ACCOUNT_TOKEN_FILE"] = str(token_file)
        if mcp_command is not None:
            env["STAGEGUARD_MCP_COMMAND"] = mcp_command
        if extra_env:
            env.update(extra_env)

        return subprocess.run(
            [sys.executable, str(DOCTOR), str(CONFIG), "--json"],
            cwd=ROOT,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=20,
        )

    @staticmethod
    def _payload(result: subprocess.CompletedProcess[str]) -> dict[str, object]:
        if result.stderr:
            # Keep assertion failures useful without accepting stderr as normal output.
            raise AssertionError(f"doctor wrote to stderr: {result.stderr}")
        return json.loads(result.stdout)

    @staticmethod
    def _checks(payload: dict[str, object]) -> dict[str, dict[str, object]]:
        checks = payload["checks"]
        assert isinstance(checks, list)
        return {str(check["name"]): check for check in checks}

    def test_ready_for_preflight_with_valid_local_prerequisites(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            token = Path(temp_dir) / "grafana-token"
            token.write_text("placeholder-test-token\n", encoding="utf-8")
            if os.name != "nt":
                token.chmod(0o600)

            result = self._run(
                token_file=token,
                mcp_command=sys.executable,
            )

        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        payload = self._payload(result)
        self.assertIs(payload["ready_for_preflight"], True)
        checks = self._checks(payload)
        self.assertEqual(checks["telemetry_config"]["status"], "ok")
        self.assertEqual(checks["grafana_url"]["status"], "ok")
        self.assertEqual(checks["grafana_token_file"]["status"], "ok")
        self.assertEqual(checks["grafana_mcp"]["status"], "ok")
        self.assertEqual(checks["metric_activation"]["required"], False)
        self.assertEqual(checks["log_activation"]["required"], False)
        self.assertTrue(
            any("runtime/preflight.py" in step for step in payload["next_steps"]),
            payload["next_steps"],
        )

    def test_missing_grafana_url_is_required_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            token = Path(temp_dir) / "grafana-token"
            token.write_text("placeholder-test-token\n", encoding="utf-8")
            result = self._run(
                grafana_url=None,
                token_file=token,
                mcp_command=sys.executable,
            )

        self.assertEqual(result.returncode, 2)
        payload = self._payload(result)
        self.assertIs(payload["ready_for_preflight"], False)
        self.assertEqual(self._checks(payload)["grafana_url"]["status"], "missing")

    def test_invalid_grafana_url_is_required_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            token = Path(temp_dir) / "grafana-token"
            token.write_text("placeholder-test-token\n", encoding="utf-8")
            result = self._run(
                grafana_url="grafana.example.invalid/no-scheme",
                token_file=token,
                mcp_command=sys.executable,
            )

        self.assertEqual(result.returncode, 2)
        payload = self._payload(result)
        self.assertEqual(self._checks(payload)["grafana_url"]["status"], "failed")

    def test_missing_token_file_is_required_failure(self) -> None:
        result = self._run(token_file=None, mcp_command=sys.executable)

        self.assertEqual(result.returncode, 2)
        payload = self._payload(result)
        self.assertEqual(self._checks(payload)["grafana_token_file"]["status"], "missing")

    def test_empty_token_file_is_required_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            token = Path(temp_dir) / "grafana-token"
            token.touch()
            result = self._run(token_file=token, mcp_command=sys.executable)

        self.assertEqual(result.returncode, 2)
        payload = self._payload(result)
        self.assertEqual(self._checks(payload)["grafana_token_file"]["status"], "failed")

    def test_missing_mcp_executable_is_required_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            token = Path(temp_dir) / "grafana-token"
            token.write_text("placeholder-test-token\n", encoding="utf-8")
            result = self._run(
                token_file=token,
                mcp_command="stageguard-definitely-missing-mcp-executable-7f84af",
            )

        self.assertEqual(result.returncode, 2)
        payload = self._payload(result)
        self.assertEqual(self._checks(payload)["grafana_mcp"]["status"], "missing")

    @unittest.skipIf(os.name == "nt", "POSIX mode-bit check is intentionally disabled on Windows")
    def test_broad_token_permissions_warn_without_blocking_preflight(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            token = Path(temp_dir) / "grafana-token"
            token.write_text("placeholder-test-token\n", encoding="utf-8")
            token.chmod(0o644)
            result = self._run(token_file=token, mcp_command=sys.executable)

        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        payload = self._payload(result)
        self.assertIs(payload["ready_for_preflight"], True)
        token_check = self._checks(payload)["grafana_token_file"]
        self.assertEqual(token_check["status"], "warning")
        self.assertIn("0o644", token_check["detail"])

    def test_optional_activation_paths_do_not_block_readiness(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            token = temp / "grafana-token"
            token.write_text("placeholder-test-token\n", encoding="utf-8")
            if os.name != "nt":
                token.chmod(stat.S_IRUSR | stat.S_IWUSR)
            missing_metric = temp / "missing-metric-activation.json"
            missing_log = temp / "missing-log-activation.json"
            result = self._run(
                token_file=token,
                mcp_command=sys.executable,
                extra_env={
                    "STAGEGUARD_METRIC_ACTIVATION": str(missing_metric),
                    "STAGEGUARD_LOG_ACTIVATION": str(missing_log),
                },
            )

        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        payload = self._payload(result)
        checks = self._checks(payload)
        self.assertIs(payload["ready_for_preflight"], True)
        self.assertEqual(checks["metric_activation"]["status"], "missing")
        self.assertEqual(checks["log_activation"]["status"], "missing")


if __name__ == "__main__":
    unittest.main()

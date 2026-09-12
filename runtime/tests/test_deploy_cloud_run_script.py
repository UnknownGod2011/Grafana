from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
DEPLOY_SCRIPT = REPO_ROOT / "scripts" / "deploy_cloud_run.sh"


@unittest.skipUnless(os.name == "posix" and shutil.which("bash"), "requires bash on a POSIX host")
class DeployCloudRunScriptTests(unittest.TestCase):
    def _base_env(self, fake_bin: Path, log_path: Path) -> dict[str, str]:
        env = os.environ.copy()
        env.update(
            {
                "PATH": f"{fake_bin}{os.pathsep}{env.get('PATH', '')}",
                "PYTHON_BIN": sys.executable,
                "PROJECT_ID": "stageguard-dev",
                "PROJECT_NUMBER": "123456789012",
                "REGION": "us-central1",
                "SERVICE_NAME": "stageguard",
                "IMAGE_URL": "us-central1-docker.pkg.dev/stageguard-dev/stageguard/stageguard:dev",
                "RUNTIME_SERVICE_ACCOUNT": "stageguard-runtime@stageguard-dev.iam.gserviceaccount.com",
                "IAP_AUDIENCE": "/projects/123456789012/global/backendServices/987654321",
                "GRAFANA_URL": "https://grafana.example.com",
                "TELEMETRY_SECRET": "stageguard-telemetry",
                "METRIC_ACTIVATION_SECRET": "stageguard-metric-activation",
                "LOG_ACTIVATION_SECRET": "stageguard-log-activation",
                "GRAFANA_TOKEN_SECRET": "stageguard-grafana-token",
                "CHECKPOINT_BUCKET": "stageguard-checkpoints-123456",
                "CHECKPOINT_HMAC_SECRET": "stageguard-checkpoint-hmac",
                "STAGEGUARD_TEST_GCLOUD_LOG": str(log_path),
            }
        )
        return env

    def _run(self, watchdog: str | None, *, include_watchdog: bool = True) -> tuple[subprocess.CompletedProcess[str], str]:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fake_bin = root / "bin"
            fake_bin.mkdir()
            log_path = root / "gcloud.log"
            fake_gcloud = fake_bin / "gcloud"
            fake_gcloud.write_text(
                "#!/usr/bin/env bash\n"
                "set -euo pipefail\n"
                "printf '%s\\n' \"$*\" >> \"${STAGEGUARD_TEST_GCLOUD_LOG}\"\n",
                encoding="utf-8",
            )
            fake_gcloud.chmod(0o755)

            env = self._base_env(fake_bin, log_path)
            env.pop("STAGEGUARD_REMEDIATION_EXECUTION_MAX_SECONDS", None)
            if include_watchdog:
                env["STAGEGUARD_REMEDIATION_EXECUTION_MAX_SECONDS"] = "" if watchdog is None else watchdog

            completed = subprocess.run(
                ["bash", str(DEPLOY_SCRIPT)],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=15,
                check=False,
            )
            log = log_path.read_text(encoding="utf-8") if log_path.exists() else ""
            return completed, log

    def test_invalid_watchdog_is_rejected_before_any_gcloud_call(self) -> None:
        for value in ("", "0", "0.5", "600.1", "nan", "inf", "-1", "1,2", "not-a-number"):
            with self.subTest(value=value):
                completed, log = self._run(value)
                self.assertEqual(completed.returncode, 2, completed.stdout + completed.stderr)
                self.assertIn(
                    "STAGEGUARD_REMEDIATION_EXECUTION_MAX_SECONDS must be between 1 and 600 seconds",
                    completed.stderr,
                )
                self.assertEqual(log, "", "unsafe config must fail before invoking gcloud")

    def test_valid_watchdog_boundaries_reach_gcloud_and_are_serialized(self) -> None:
        for value in ("1", "17.5", "600"):
            with self.subTest(value=value):
                completed, log = self._run(value)
                self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
                lines = [line for line in log.splitlines() if line]
                self.assertEqual(len(lines), 2, lines)
                self.assertTrue(lines[0].startswith("run deploy stageguard "), lines[0])
                self.assertIn(
                    f"STAGEGUARD_REMEDIATION_EXECUTION_MAX_SECONDS={value}",
                    lines[0],
                )
                self.assertTrue(lines[1].startswith("run services add-iam-policy-binding stageguard "), lines[1])

    def test_unset_watchdog_uses_safe_default(self) -> None:
        completed, log = self._run(None, include_watchdog=False)
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("STAGEGUARD_REMEDIATION_EXECUTION_MAX_SECONDS=60", log)


if __name__ == "__main__":
    unittest.main()

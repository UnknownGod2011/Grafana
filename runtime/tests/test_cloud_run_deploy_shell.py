from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy_cloud_run.sh"


class CloudRunDeployShellTests(unittest.TestCase):
    def _run_deploy(self, checkpoint_object: str) -> tuple[subprocess.CompletedProcess[str], str]:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            bin_dir = tmp_path / "bin"
            bin_dir.mkdir()
            calls = tmp_path / "gcloud-calls.txt"
            fake_gcloud = bin_dir / "gcloud"
            fake_gcloud.write_text(
                "#!/usr/bin/env sh\n"
                "printf '%s\\n' \"$*\" >> \"$STAGEGUARD_TEST_GCLOUD_CALLS\"\n",
                encoding="utf-8",
            )
            fake_gcloud.chmod(0o755)

            env = os.environ.copy()
            env.update(
                {
                    "PATH": f"{bin_dir}{os.pathsep}{env.get('PATH', '')}",
                    "STAGEGUARD_TEST_GCLOUD_CALLS": str(calls),
                    "PROJECT_ID": "stageguard-test-project",
                    "PROJECT_NUMBER": "123456789012",
                    "REGION": "us-central1",
                    "SERVICE_NAME": "stageguard-test",
                    "IMAGE_URL": "us-central1-docker.pkg.dev/stageguard-test-project/stageguard/runtime:test",
                    "RUNTIME_SERVICE_ACCOUNT": "stageguard-runtime@stageguard-test-project.iam.gserviceaccount.com",
                    "IAP_AUDIENCE": "/projects/123456789012/global/backendServices/1234567890",
                    "GRAFANA_URL": "https://stageguard.example.grafana.net",
                    "TELEMETRY_SECRET": "stageguard-telemetry",
                    "METRIC_ACTIVATION_SECRET": "stageguard-metric-activation",
                    "LOG_ACTIVATION_SECRET": "stageguard-log-activation",
                    "GRAFANA_TOKEN_SECRET": "stageguard-grafana-token",
                    "CHECKPOINT_BUCKET": "stageguard-test-checkpoints",
                    "CHECKPOINT_HMAC_SECRET": "stageguard-checkpoint-hmac",
                    "CHECKPOINT_OBJECT": checkpoint_object,
                    "ENABLE_GEMINI": "false",
                }
            )
            result = subprocess.run(
                ["bash", str(DEPLOY)],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
                timeout=15,
            )
            call_text = calls.read_text(encoding="utf-8") if calls.exists() else ""
            return result, call_text

    def test_exactly_512_ascii_bytes_reaches_fake_gcloud(self) -> None:
        result, calls = self._run_deploy("a" * 512)
        self.assertEqual(result.returncode, 0, result.stderr)
        lines = [line for line in calls.splitlines() if line]
        self.assertEqual(len(lines), 2)
        self.assertTrue(lines[0].startswith("run deploy stageguard-test"), lines[0])
        self.assertTrue(lines[1].startswith("run services add-iam-policy-binding stageguard-test"), lines[1])

    def test_513_ascii_bytes_fails_before_gcloud(self) -> None:
        result, calls = self._run_deploy("a" * 513)
        self.assertEqual(result.returncode, 2)
        self.assertIn("CHECKPOINT_OBJECT must be at most 512 UTF-8 bytes", result.stderr)
        self.assertEqual(calls, "")

    def test_multibyte_value_over_512_utf8_bytes_fails_before_gcloud(self) -> None:
        checkpoint_object = "é" * 300
        self.assertLessEqual(len(checkpoint_object), 512)
        self.assertGreater(len(checkpoint_object.encode("utf-8")), 512)
        result, calls = self._run_deploy(checkpoint_object)
        self.assertEqual(result.returncode, 2)
        self.assertIn("CHECKPOINT_OBJECT must be at most 512 UTF-8 bytes", result.stderr)
        self.assertEqual(calls, "")

    def test_leading_whitespace_fails_before_gcloud(self) -> None:
        result, calls = self._run_deploy(" stageguard/checkpoint.json")
        self.assertEqual(result.returncode, 2)
        self.assertIn("CHECKPOINT_OBJECT is not a valid bounded object path", result.stderr)
        self.assertEqual(calls, "")

    def test_trailing_whitespace_fails_before_gcloud(self) -> None:
        result, calls = self._run_deploy("stageguard/checkpoint.json ")
        self.assertEqual(result.returncode, 2)
        self.assertIn("CHECKPOINT_OBJECT is not a valid bounded object path", result.stderr)
        self.assertEqual(calls, "")


if __name__ == "__main__":
    unittest.main()

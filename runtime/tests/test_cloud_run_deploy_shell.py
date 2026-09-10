from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy_cloud_run.sh"


class CloudRunDeployShellTests(unittest.TestCase):
    def _run_deploy(
        self,
        checkpoint_object: str = "stageguard/incident-checkpoint.json",
        overrides: dict[str, str] | None = None,
    ) -> tuple[subprocess.CompletedProcess[str], str]:
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
            if overrides:
                env.update(overrides)
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

    def _assert_rejected_before_gcloud(self, overrides: dict[str, str], message: str) -> None:
        result, calls = self._run_deploy(overrides=overrides)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn(message, result.stderr)
        self.assertEqual(calls, "")

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

    def test_checkpoint_hmac_payload_env_is_never_forwarded(self) -> None:
        sentinel = "TOP-SECRET-HMAC-PAYLOAD-MUST-NOT-LEAK"
        result, calls = self._run_deploy(
            overrides={"STAGEGUARD_CHECKPOINT_HMAC_KEY": sentinel}
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn(sentinel, calls)
        deploy_call = calls.splitlines()[0]
        self.assertIn("STAGEGUARD_CHECKPOINT_HMAC_KEY=stageguard-checkpoint-hmac:latest", deploy_call)
        self.assertNotIn("--set-env-vars=STAGEGUARD_CHECKPOINT_HMAC_KEY", deploy_call)

    def test_grafana_url_comma_injection_fails_before_gcloud(self) -> None:
        self._assert_rejected_before_gcloud(
            {"GRAFANA_URL": "https://grafana.example.net,INJECTED=true"},
            "GRAFANA_URL must be an absolute http(s) URL without commas or whitespace",
        )

    def test_iap_audience_comma_injection_fails_before_gcloud(self) -> None:
        self._assert_rejected_before_gcloud(
            {"IAP_AUDIENCE": "/projects/1/global/backendServices/2,INJECTED=true"},
            "IAP_AUDIENCE must be a non-empty value without commas, whitespace, or control characters",
        )

    def test_secret_mapping_injection_fails_before_gcloud(self) -> None:
        self._assert_rejected_before_gcloud(
            {"CHECKPOINT_HMAC_SECRET": "checkpoint-hmac,INJECTED=other-secret"},
            "CHECKPOINT_HMAC_SECRET must be a Secret Manager secret ID",
        )

    def test_malformed_runtime_service_account_fails_before_gcloud(self) -> None:
        self._assert_rejected_before_gcloud(
            {"RUNTIME_SERVICE_ACCOUNT": "runtime@example.com,INJECTED=true"},
            "RUNTIME_SERVICE_ACCOUNT must be a service-account email",
        )

    def test_nonnumeric_project_number_fails_before_gcloud(self) -> None:
        self._assert_rejected_before_gcloud(
            {"PROJECT_NUMBER": "123,INJECTED"},
            "PROJECT_NUMBER must contain digits only",
        )

    def test_invalid_enable_gemini_fails_before_gcloud(self) -> None:
        self._assert_rejected_before_gcloud(
            {"ENABLE_GEMINI": "treu"},
            "ENABLE_GEMINI must be true or false",
        )

    def test_invalid_gemini_location_fails_before_gcloud(self) -> None:
        self._assert_rejected_before_gcloud(
            {"ENABLE_GEMINI": "true", "GOOGLE_CLOUD_LOCATION": "us-central1,INJECTED=true"},
            "GOOGLE_CLOUD_LOCATION must be a non-empty value without commas or whitespace",
        )

    def test_invalid_gemini_model_fails_before_gcloud(self) -> None:
        self._assert_rejected_before_gcloud(
            {"ENABLE_GEMINI": "true", "STAGEGUARD_GEMINI_MODEL": "gemini-2.5-flash INJECTED"},
            "STAGEGUARD_GEMINI_MODEL must be a non-empty value without commas or whitespace",
        )


if __name__ == "__main__":
    unittest.main()

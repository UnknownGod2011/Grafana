from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DOCTOR = ROOT / "scripts" / "gcp_deploy_doctor.py"

VALID_ENV = {
    "PROJECT_ID": "stageguard-test",
    "PROJECT_NUMBER": "123456789012",
    "REGION": "us-central1",
    "SERVICE_NAME": "stageguard",
    "IMAGE_URL": "us-central1-docker.pkg.dev/stageguard-test/stageguard/api:test",
    "RUNTIME_SERVICE_ACCOUNT": "stageguard@stageguard-test.iam.gserviceaccount.com",
    "IAP_AUDIENCE": "/projects/123456789012/global/backendServices/1234567890",
    "GRAFANA_URL": "https://example.grafana.net",
    "TELEMETRY_SECRET": "stageguard-telemetry",
    "METRIC_ACTIVATION_SECRET": "stageguard-metric-activation",
    "LOG_ACTIVATION_SECRET": "stageguard-log-activation",
    "GRAFANA_TOKEN_SECRET": "stageguard-grafana-token",
    "CHECKPOINT_BUCKET": "stageguard-checkpoints-test",
    "CHECKPOINT_HMAC_SECRET": "stageguard-checkpoint-hmac",
    "CHECKPOINT_OBJECT": "stageguard/incident-checkpoint.json",
    "ENABLE_GEMINI": "false",
}


class GcpDeployDoctorSerializationTests(unittest.TestCase):
    def _run(self, overrides: dict[str, str]) -> tuple[subprocess.CompletedProcess[str], dict[str, dict[str, object]]]:
        env = os.environ.copy()
        env.update(VALID_ENV)
        env.update(overrides)
        result = subprocess.run(
            [sys.executable, str(DOCTOR), "--offline", "--json"],
            cwd=ROOT,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=20,
        )
        self.assertFalse(result.stderr, result.stderr)
        payload = json.loads(result.stdout)
        checks = {str(check["name"]): check for check in payload["checks"]}
        return result, checks

    def test_valid_environment_passes_offline_serialization_checks(self) -> None:
        result, checks = self._run({})
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(checks["project_id_format"]["status"], "ok")
        self.assertEqual(checks["region_format"]["status"], "ok")
        self.assertEqual(checks["service_name_format"]["status"], "ok")
        self.assertEqual(checks["image_url_cli_safety"]["status"], "ok")
        self.assertEqual(checks["image_url_format"]["status"], "ok")
        self.assertEqual(checks["iap_audience_format"]["status"], "ok")
        for name in (
            "TELEMETRY_SECRET",
            "METRIC_ACTIVATION_SECRET",
            "LOG_ACTIVATION_SECRET",
            "GRAFANA_TOKEN_SECRET",
            "CHECKPOINT_HMAC_SECRET",
        ):
            self.assertEqual(checks[f"secret_id_format:{name}"]["status"], "ok")

    def test_iap_audience_mapping_injection_fails_offline(self) -> None:
        result, checks = self._run({"IAP_AUDIENCE": "/projects/1/global/backendServices/2,INJECTED=true"})
        self.assertEqual(result.returncode, 2)
        self.assertEqual(checks["iap_audience_format"]["status"], "failed")

    def test_image_mapping_injection_fails_offline(self) -> None:
        result, checks = self._run({"IMAGE_URL": "us-central1-docker.pkg.dev/p/r/i:test,INJECTED=true"})
        self.assertEqual(result.returncode, 2)
        self.assertEqual(checks["image_url_cli_safety"]["status"], "failed")

    def test_secret_name_mapping_injection_fails_offline(self) -> None:
        result, checks = self._run({"GRAFANA_TOKEN_SECRET": "grafana-token,INJECTED=other"})
        self.assertEqual(result.returncode, 2)
        self.assertEqual(checks["secret_id_format:GRAFANA_TOKEN_SECRET"]["status"], "failed")

    def test_secret_name_length_is_bounded(self) -> None:
        result, checks = self._run({"CHECKPOINT_HMAC_SECRET": "a" * 256})
        self.assertEqual(result.returncode, 2)
        self.assertEqual(checks["secret_id_format:CHECKPOINT_HMAC_SECRET"]["status"], "failed")

    def test_invalid_project_id_fails_with_shared_validator(self) -> None:
        result, checks = self._run({"PROJECT_ID": "StageGuard-Test"})
        self.assertEqual(result.returncode, 2)
        self.assertEqual(checks["project_id_format"]["status"], "failed")

    def test_invalid_region_fails_with_shared_validator(self) -> None:
        result, checks = self._run({"REGION": "uscentral1"})
        self.assertEqual(result.returncode, 2)
        self.assertEqual(checks["region_format"]["status"], "failed")

    def test_invalid_service_name_fails_with_shared_validator(self) -> None:
        result, checks = self._run({"SERVICE_NAME": "StageGuard"})
        self.assertEqual(result.returncode, 2)
        self.assertEqual(checks["service_name_format"]["status"], "failed")

    def test_unversioned_artifact_registry_image_is_required_failure(self) -> None:
        result, checks = self._run({"IMAGE_URL": "us-central1-docker.pkg.dev/stageguard-test/stageguard/api"})
        self.assertEqual(result.returncode, 2)
        self.assertEqual(checks["image_url_format"]["status"], "failed")
        self.assertTrue(checks["image_url_format"]["required"])

    def test_non_artifact_registry_image_is_required_failure(self) -> None:
        result, checks = self._run({"IMAGE_URL": "docker.io/example/stageguard:test"})
        self.assertEqual(result.returncode, 2)
        self.assertEqual(checks["image_url_format"]["status"], "failed")

    def test_cross_project_artifact_registry_image_is_allowed(self) -> None:
        result, checks = self._run({"IMAGE_URL": "us-central1-docker.pkg.dev/shared-images/stageguard/api:test"})
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(checks["image_url_format"]["status"], "ok")


if __name__ == "__main__":
    unittest.main()

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
}


class GcpDeployDoctorOfflineTests(unittest.TestCase):
    def _run(self, overrides: dict[str, str | None] | None = None) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        for name in VALID_ENV:
            env.pop(name, None)
        env.update(VALID_ENV)
        for name, value in (overrides or {}).items():
            if value is None:
                env.pop(name, None)
            else:
                env[name] = value

        return subprocess.run(
            [sys.executable, str(DOCTOR), "--offline", "--json"],
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
            raise AssertionError(f"doctor wrote to stderr: {result.stderr}")
        return json.loads(result.stdout)

    @staticmethod
    def _checks(payload: dict[str, object]) -> dict[str, dict[str, object]]:
        checks = payload["checks"]
        assert isinstance(checks, list)
        return {str(check["name"]): check for check in checks}

    def test_valid_offline_environment_requires_live_validation_before_deploy(self) -> None:
        result = self._run()
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        payload = self._payload(result)
        self.assertIs(payload["offline_checks_passed"], True)
        self.assertIs(payload["ready_to_deploy"], False)
        self.assertTrue(any("gcp_deploy_doctor.py --json" in step for step in payload["next_steps"]))

    def test_missing_required_variable_fails(self) -> None:
        result = self._run({"PROJECT_ID": None})
        self.assertEqual(result.returncode, 2)
        payload = self._payload(result)
        self.assertIs(payload["offline_checks_passed"], False)
        self.assertEqual(self._checks(payload)["env:PROJECT_ID"]["status"], "missing")

    def test_project_number_must_be_numeric(self) -> None:
        result = self._run({"PROJECT_NUMBER": "not-a-number"})
        self.assertEqual(result.returncode, 2)
        payload = self._payload(result)
        self.assertEqual(self._checks(payload)["project_number_format"]["status"], "failed")

    def test_grafana_url_rejects_non_absolute_value(self) -> None:
        result = self._run({"GRAFANA_URL": "grafana.example.invalid"})
        self.assertEqual(result.returncode, 2)
        payload = self._payload(result)
        self.assertEqual(self._checks(payload)["grafana_url_format"]["status"], "failed")

    def test_runtime_service_account_requires_service_account_domain(self) -> None:
        result = self._run({"RUNTIME_SERVICE_ACCOUNT": "operator@example.com"})
        self.assertEqual(result.returncode, 2)
        payload = self._payload(result)
        self.assertEqual(self._checks(payload)["runtime_service_account_format"]["status"], "failed")

    def test_non_artifact_registry_image_is_advisory_only(self) -> None:
        result = self._run({"IMAGE_URL": "example.com/stageguard/api:test"})
        self.assertEqual(result.returncode, 0)
        payload = self._payload(result)
        check = self._checks(payload)["image_url_format"]
        self.assertEqual(check["status"], "warning")
        self.assertIs(check["required"], False)


if __name__ == "__main__":
    unittest.main()

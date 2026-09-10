from __future__ import annotations

import importlib.util
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


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


def _load_doctor_module():
    scripts_dir = str(DOCTOR.parent)
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    spec = importlib.util.spec_from_file_location("stageguard_gcp_deploy_doctor_process_failure_tests", DOCTOR)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load gcp_deploy_doctor.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class GcloudRunnerFailureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.doctor = _load_doctor_module()

    def test_timeout_is_sanitized_without_command_context(self) -> None:
        secret_marker = "stageguard-super-sensitive-secret-name"
        timeout = subprocess.TimeoutExpired(
            cmd=["gcloud", "secrets", "describe", secret_marker],
            timeout=self.doctor.GCLOUD_TIMEOUT_SECONDS,
        )
        with mock.patch.object(self.doctor.subprocess, "run", side_effect=timeout):
            code, stdout, stderr = self.doctor._run_gcloud(["secrets", "describe", secret_marker])

        self.assertEqual(code, self.doctor.GCLOUD_TIMEOUT_EXIT_CODE)
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "gcloud command timed out")
        self.assertNotIn(secret_marker, stderr)

    def test_os_invocation_failure_is_sanitized(self) -> None:
        with mock.patch.object(self.doctor.subprocess, "run", side_effect=FileNotFoundError("/tmp/private/gcloud vanished")):
            code, stdout, stderr = self.doctor._run_gcloud(["auth", "list"])

        self.assertEqual(code, self.doctor.GCLOUD_EXECUTION_EXIT_CODE)
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "gcloud command could not be executed")
        self.assertNotIn("/tmp/private", stderr)

    def test_decode_failure_is_sanitized(self) -> None:
        decode_error = UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid start byte")
        with mock.patch.object(self.doctor.subprocess, "run", side_effect=decode_error):
            code, stdout, stderr = self.doctor._run_gcloud(["auth", "list"])

        self.assertEqual(code, self.doctor.GCLOUD_EXECUTION_EXIT_CODE)
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "gcloud command could not be executed")

    def test_gcloud_checks_turn_runner_failure_into_required_check(self) -> None:
        with mock.patch.object(self.doctor.shutil, "which", return_value="/usr/bin/gcloud"), mock.patch.object(
            self.doctor,
            "_run_gcloud",
            return_value=(self.doctor.GCLOUD_TIMEOUT_EXIT_CODE, "", "gcloud command timed out"),
        ):
            checks = self.doctor._gcloud_checks()

        by_name = {check.name: check for check in checks}
        self.assertEqual(by_name["gcloud"].status, "ok")
        self.assertEqual(by_name["gcloud_auth"].status, "failed")
        self.assertTrue(by_name["gcloud_auth"].required)


@unittest.skipIf(os.name == "nt", "fake gcloud executable harness currently targets POSIX deployment environments")
class GcloudSubprocessFailureTests(unittest.TestCase):
    def test_nonzero_gcloud_failure_still_emits_structured_json(self) -> None:
        fake_source = """#!/usr/bin/env python3
import sys
print('synthetic gcloud failure', file=sys.stderr)
raise SystemExit(125)
"""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            fake = temp / "gcloud"
            fake.write_text(fake_source, encoding="utf-8")
            fake.chmod(fake.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

            env = os.environ.copy()
            env.update(VALID_ENV)
            env["PATH"] = str(temp) + os.pathsep + env.get("PATH", "")
            result = subprocess.run(
                [sys.executable, str(DOCTOR), "--json"],
                cwd=ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                timeout=20,
            )

        self.assertEqual(result.returncode, 2, result.stderr or result.stdout)
        self.assertEqual(result.stderr, "")
        payload = json.loads(result.stdout)
        checks = {str(check["name"]): check for check in payload["checks"]}
        self.assertIs(payload["ready_to_deploy"], False)
        self.assertEqual(checks["gcloud_auth"]["status"], "failed")
        self.assertNotIn("synthetic gcloud failure", result.stdout)
        self.assertNotIn("Traceback", result.stdout)


if __name__ == "__main__":
    unittest.main()

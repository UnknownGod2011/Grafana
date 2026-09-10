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

FAKE_GCLOUD = r'''#!/usr/bin/env python3
import json
import os
import sys

args = sys.argv[1:]
log_path = os.environ.get("FAKE_GCLOUD_LOG")
if log_path:
    with open(log_path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(args) + "\n")

if args[:2] == ["auth", "list"]:
    print("operator@example.com")
    raise SystemExit(0)

if args[:2] == ["projects", "describe"]:
    print("123456789012")
    raise SystemExit(0)

if args[:3] == ["run", "regions", "list"]:
    print(os.environ.get("FAKE_GCLOUD_REGIONS", "us-central1\nasia-south1"))
    raise SystemExit(0)

if args[:2] == ["services", "list"]:
    print("\n".join([
        "run.googleapis.com",
        "iap.googleapis.com",
        "secretmanager.googleapis.com",
        "logging.googleapis.com",
        "policytroubleshooter.googleapis.com",
        "storage.googleapis.com",
    ]))
    raise SystemExit(0)

if args[:2] == ["secrets", "describe"]:
    print(args[2])
    raise SystemExit(0)

if args[:3] == ["storage", "buckets", "describe"]:
    print("stageguard-checkpoints-test")
    raise SystemExit(0)

if args[:4] == ["artifacts", "docker", "images", "describe"]:
    print("sha256:" + "a" * 64)
    raise SystemExit(0)

if args[:3] == ["policy-intelligence", "troubleshoot-policy", "iam"]:
    denied = os.environ.get("FAKE_GCLOUD_DENY_PERMISSION", "")
    permission = next((item.split("=", 1)[1] for item in args if item.startswith("--permission=")), "")
    state = "CANNOT_ACCESS" if permission == denied else "CAN_ACCESS"
    print(json.dumps({"overallAccessState": state}))
    raise SystemExit(0)

print("unsupported fake gcloud invocation: " + repr(args), file=sys.stderr)
raise SystemExit(91)
'''


@unittest.skipIf(os.name == "nt", "fake gcloud executable harness currently targets POSIX deployment environments")
class GcpDeployDoctorFakeGcloudTests(unittest.TestCase):
    def _run(self, *, regions: str = "us-central1\nasia-south1", deny_permission: str = ""):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            fake = temp / "gcloud"
            fake.write_text(FAKE_GCLOUD, encoding="utf-8")
            fake.chmod(fake.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
            command_log = temp / "gcloud.jsonl"

            env = os.environ.copy()
            env.update(VALID_ENV)
            env["PATH"] = str(temp) + os.pathsep + env.get("PATH", "")
            env["FAKE_GCLOUD_LOG"] = str(command_log)
            env["FAKE_GCLOUD_REGIONS"] = regions
            env["FAKE_GCLOUD_DENY_PERMISSION"] = deny_permission

            result = subprocess.run(
                [sys.executable, str(DOCTOR), "--json"],
                cwd=ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                timeout=30,
            )
            calls = []
            if command_log.exists():
                calls = [json.loads(line) for line in command_log.read_text(encoding="utf-8").splitlines() if line]
            return result, calls

    @staticmethod
    def _payload(result: subprocess.CompletedProcess[str]) -> dict[str, object]:
        if result.stderr:
            raise AssertionError(f"doctor wrote to stderr: {result.stderr}")
        return json.loads(result.stdout)

    @staticmethod
    def _checks(payload: dict[str, object]) -> dict[str, dict[str, object]]:
        raw = payload["checks"]
        assert isinstance(raw, list)
        return {str(check["name"]): check for check in raw}

    def test_supported_region_can_complete_full_read_only_preflight(self) -> None:
        result, calls = self._run()
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        payload = self._payload(result)
        checks = self._checks(payload)

        self.assertIs(payload["ready_to_deploy"], True)
        self.assertEqual(checks["cloud_run_region_available"]["status"], "ok")
        self.assertEqual(checks["apis"]["status"], "ok")
        self.assertEqual(checks["checkpoint_bucket_exists"]["status"], "ok")
        self.assertEqual(checks["image_exists"]["status"], "ok")
        for suffix in ("get", "create", "delete"):
            self.assertEqual(checks[f"checkpoint_storage_access:{suffix}"]["status"], "ok")
        for suffix in ("create", "list"):
            self.assertEqual(checks[f"logging_access:{suffix}"]["status"], "ok")

        self.assertTrue(any(call[:3] == ["run", "regions", "list"] for call in calls))
        self.assertTrue(any(call[:2] == ["services", "list"] for call in calls))
        self.assertTrue(any(call[:3] == ["storage", "buckets", "describe"] for call in calls))
        self.assertTrue(any(call[:4] == ["artifacts", "docker", "images", "describe"] for call in calls))
        troubleshoot_calls = [call for call in calls if call[:3] == ["policy-intelligence", "troubleshoot-policy", "iam"]]
        self.assertEqual(len(troubleshoot_calls), 10)

    def test_unsupported_region_fails_closed_but_still_collects_remaining_evidence(self) -> None:
        result, calls = self._run(regions="asia-south1\neurope-west1")
        self.assertEqual(result.returncode, 2, result.stderr or result.stdout)
        payload = self._payload(result)
        checks = self._checks(payload)

        self.assertIs(payload["ready_to_deploy"], False)
        self.assertEqual(checks["cloud_run_region_available"]["status"], "failed")
        self.assertEqual(checks["apis"]["status"], "ok")
        self.assertEqual(checks["checkpoint_bucket_exists"]["status"], "ok")
        self.assertEqual(checks["image_exists"]["status"], "ok")
        self.assertTrue(any("gcloud run regions list" in step for step in payload["next_steps"]))
        self.assertTrue(any(call[:4] == ["artifacts", "docker", "images", "describe"] for call in calls))

    def test_empty_region_catalog_fails_closed(self) -> None:
        result, _ = self._run(regions="\n")
        self.assertEqual(result.returncode, 2, result.stderr or result.stdout)
        payload = self._payload(result)
        check = self._checks(payload)["cloud_run_region_available"]
        self.assertEqual(check["status"], "failed")
        self.assertIn("no usable locations", str(check["detail"]))

    def test_denied_runtime_permission_keeps_ready_false(self) -> None:
        result, _ = self._run(deny_permission="storage.objects.delete")
        self.assertEqual(result.returncode, 2, result.stderr or result.stdout)
        payload = self._payload(result)
        checks = self._checks(payload)
        self.assertIs(payload["ready_to_deploy"], False)
        self.assertEqual(checks["checkpoint_storage_access:delete"]["status"], "failed")
        self.assertEqual(checks["checkpoint_storage_access:get"]["status"], "ok")
        self.assertEqual(checks["checkpoint_storage_access:create"]["status"], "ok")


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
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
    spec = importlib.util.spec_from_file_location("stageguard_gcp_deploy_doctor_test_module", DOCTOR)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load gcp_deploy_doctor.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


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
        self.assertIs(payload["gemini_enabled"], False)
        self.assertEqual(payload["checkpoint_bucket"], "stageguard-checkpoints-test")
        self.assertEqual(payload["checkpoint_object"], "stageguard/incident-checkpoint.json")
        self.assertIn("storage.googleapis.com", payload["required_apis"])
        self.assertIn("policytroubleshooter.googleapis.com", payload["required_apis"])
        self.assertNotIn("aiplatform.googleapis.com", payload["required_apis"])
        self.assertTrue(any("gcp_deploy_doctor.py --json" in step for step in payload["next_steps"]))

    def test_missing_required_checkpoint_values_fail(self) -> None:
        for name in ("CHECKPOINT_BUCKET", "CHECKPOINT_HMAC_SECRET"):
            with self.subTest(name=name):
                result = self._run({name: None})
                self.assertEqual(result.returncode, 2)
                payload = self._payload(result)
                self.assertEqual(self._checks(payload)[f"env:{name}"]["status"], "missing")

    def test_checkpoint_bucket_matches_runtime_boundary(self) -> None:
        for value in ("Abc-bucket", "12.34.56.78", "foo..bar", "google-data", "ab"):
            with self.subTest(value=value):
                result = self._run({"CHECKPOINT_BUCKET": value})
                self.assertEqual(result.returncode, 2)
                self.assertEqual(self._checks(self._payload(result))["checkpoint_bucket_format"]["status"], "failed")

    def test_checkpoint_object_matches_runtime_boundary(self) -> None:
        for value in ("/stageguard/checkpoint.json", "stageguard/../checkpoint.json", "stageguard//checkpoint.json", "stageguard,checkpoint.json", "stageguard\\checkpoint.json", " stageguard/checkpoint.json"):
            with self.subTest(value=value):
                result = self._run({"CHECKPOINT_OBJECT": value})
                self.assertEqual(result.returncode, 2)
                self.assertEqual(self._checks(self._payload(result))["checkpoint_object_format"]["status"], "failed")

    def test_project_number_and_grafana_and_service_account_validation(self) -> None:
        cases = (
            ({"PROJECT_NUMBER": "not-a-number"}, "project_number_format"),
            ({"GRAFANA_URL": "grafana.example.invalid"}, "grafana_url_format"),
            ({"RUNTIME_SERVICE_ACCOUNT": "operator@example.com"}, "runtime_service_account_format"),
        )
        for overrides, check_name in cases:
            with self.subTest(check=check_name):
                result = self._run(overrides)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(self._checks(self._payload(result))[check_name]["status"], "failed")

    def test_non_artifact_registry_image_fails_closed(self) -> None:
        result = self._run({"IMAGE_URL": "example.com/stageguard/api:test"})
        self.assertEqual(result.returncode, 2)
        check = self._checks(self._payload(result))["image_url_format"]
        self.assertEqual(check["status"], "failed")
        self.assertIs(check["required"], True)

    def test_gemini_contract_and_boolean_aliases(self) -> None:
        result = self._run({"ENABLE_GEMINI": "true"})
        self.assertEqual(result.returncode, 0)
        payload = self._payload(result)
        self.assertIs(payload["gemini_enabled"], True)
        self.assertIn("aiplatform.googleapis.com", payload["required_apis"])
        self.assertEqual(payload["gemini_location"], "global")
        self.assertEqual(payload["gemini_model"], "gemini-2.5-flash")
        for value in ("1", "yes", "on", "TRUE", "0", "no", "off", "FALSE"):
            with self.subTest(value=value):
                alias = self._run({"ENABLE_GEMINI": value})
                self.assertEqual(alias.returncode, 0)
                expected = value.strip().lower() in {"1", "true", "yes", "on"}
                self.assertIs(self._payload(alias)["gemini_enabled"], expected)

    def test_invalid_gemini_and_runtime_identifiers_fail(self) -> None:
        result = self._run({"ENABLE_GEMINI": "maybe"})
        self.assertEqual(result.returncode, 2)
        self.assertEqual(self._checks(self._payload(result))["enable_gemini_format"]["status"], "failed")
        result = self._run({"ENABLE_GEMINI": "true", "GOOGLE_CLOUD_LOCATION": "https://us-central1-aiplatform.googleapis.com", "STAGEGUARD_GEMINI_MODEL": "publishers/google/models/gemini-2.5-flash"})
        self.assertEqual(result.returncode, 2)
        checks = self._checks(self._payload(result))
        self.assertEqual(checks["gemini_location_format"]["status"], "failed")
        self.assertEqual(checks["gemini_model_format"]["status"], "failed")


class GcpDeployDoctorPermissionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.doctor = _load_doctor_module()

    def _response(self, func, *args, state="CAN_ACCESS"):
        with mock.patch.object(self.doctor, "_run_gcloud", return_value=(0, json.dumps({"overallAccessState": state}), "")) as run:
            check = func(*args)
        return check, run

    def test_secret_access_uses_policy_troubleshooter_without_payload_read(self) -> None:
        check, run = self._response(self.doctor._secret_access_check, "123456789012", "stageguard@stageguard-test.iam.gserviceaccount.com", "stageguard-grafana-token", "GRAFANA_TOKEN_SECRET")
        self.assertEqual(check.status, "ok")
        self.assertIn("payload not read", check.detail)
        args = run.call_args.args[0]
        self.assertIn("//secretmanager.googleapis.com/projects/123456789012/secrets/stageguard-grafana-token", args)
        self.assertIn("--permission=secretmanager.versions.access", args)

    def test_logging_permissions_match_runtime_contract(self) -> None:
        self.assertEqual(self.doctor.LOGGING_RUNTIME_PERMISSIONS, ("logging.logEntries.create", "logging.logEntries.list"))
        check, run = self._response(self.doctor._logging_access_check, "stageguard-test", "stageguard@stageguard-test.iam.gserviceaccount.com", "logging.logEntries.create")
        self.assertEqual(check.status, "ok")
        self.assertIn("//cloudresourcemanager.googleapis.com/projects/stageguard-test", run.call_args.args[0])

    def test_checkpoint_permissions_are_exact_and_object_scoped(self) -> None:
        self.assertEqual(self.doctor.STORAGE_RUNTIME_PERMISSIONS, ("storage.objects.get", "storage.objects.create", "storage.objects.delete"))
        for permission in self.doctor.STORAGE_RUNTIME_PERMISSIONS:
            with self.subTest(permission=permission):
                check, run = self._response(
                    self.doctor._storage_access_check,
                    "stageguard-checkpoints-test",
                    "stageguard/incident-checkpoint.json",
                    "stageguard@stageguard-test.iam.gserviceaccount.com",
                    permission,
                )
                self.assertEqual(check.status, "ok")
                args = run.call_args.args[0]
                self.assertIn("//storage.googleapis.com/projects/_/buckets/stageguard-checkpoints-test/objects/stageguard/incident-checkpoint.json", args)
                self.assertIn(f"--permission={permission}", args)
                self.assertNotIn("--permission=storage.objects.list", args)

    def test_checkpoint_access_denied_or_unknown_fails_closed(self) -> None:
        for state in ("CANNOT_ACCESS", "UNKNOWN"):
            with self.subTest(state=state):
                check, _ = self._response(
                    self.doctor._storage_access_check,
                    "stageguard-checkpoints-test",
                    "stageguard/incident-checkpoint.json",
                    "stageguard@stageguard-test.iam.gserviceaccount.com",
                    "storage.objects.get",
                    state=state,
                )
                self.assertEqual(check.status, "failed")

    def test_policy_troubleshooter_command_and_json_fail_closed(self) -> None:
        with mock.patch.object(self.doctor, "_run_gcloud", return_value=(1, "", "")):
            failed = self.doctor._storage_access_check("stageguard-checkpoints-test", "stageguard/incident-checkpoint.json", "stageguard@stageguard-test.iam.gserviceaccount.com", "storage.objects.get")
        self.assertEqual(failed.status, "failed")
        with mock.patch.object(self.doctor, "_run_gcloud", return_value=(0, "not-json", "")):
            malformed = self.doctor._storage_access_check("stageguard-checkpoints-test", "stageguard/incident-checkpoint.json", "stageguard@stageguard-test.iam.gserviceaccount.com", "storage.objects.get")
        self.assertEqual(malformed.status, "failed")

    def test_vertex_permission_matches_generate_content_contract(self) -> None:
        self.assertEqual(self.doctor.VERTEX_PREDICT_PERMISSION, "aiplatform.endpoints.predict")
        check, run = self._response(self.doctor._vertex_predict_access_check, "stageguard-test", "stageguard@stageguard-test.iam.gserviceaccount.com", "global", "gemini-2.5-flash")
        self.assertEqual(check.status, "ok")
        args = run.call_args.args[0]
        self.assertIn("//aiplatform.googleapis.com/projects/stageguard-test/locations/global/publishers/google/models/gemini-2.5-flash", args)
        self.assertIn("--permission=aiplatform.endpoints.predict", args)

    def test_cloud_run_region_check_uses_live_provider_catalog(self) -> None:
        with mock.patch.object(self.doctor, "_run_gcloud", return_value=(0, "asia-south1\nus-central1\neurope-west1\n", "")) as run:
            check = self.doctor._cloud_run_region_check("stageguard-test", "us-central1")
        self.assertEqual(check.status, "ok")
        self.assertEqual(
            run.call_args.args[0],
            ["run", "regions", "list", "--project=stageguard-test", "--format=value(locationId)"],
        )

    def test_cloud_run_region_check_fails_closed_for_missing_or_unreadable_catalog(self) -> None:
        cases = (
            ((0, "asia-south1\neurope-west1\n", ""), "us-central1"),
            ((0, "\n", ""), "us-central1"),
            ((1, "", "permission denied"), "us-central1"),
        )
        for response, region in cases:
            with self.subTest(response=response):
                with mock.patch.object(self.doctor, "_run_gcloud", return_value=response):
                    check = self.doctor._cloud_run_region_check("stageguard-test", region)
                self.assertEqual(check.status, "failed")
                self.assertTrue(check.required)

    def test_next_steps_explain_live_region_contract(self) -> None:
        checks = [self.doctor.Check("cloud_run_region_available", "failed", "not available")]
        steps = self.doctor._next_steps(checks, offline=False)
        self.assertTrue(any("gcloud run regions list" in step for step in steps))

    def test_next_steps_explain_least_privilege_storage_contract(self) -> None:
        checks = [self.doctor.Check("checkpoint_storage_access:delete", "failed", "denied")]
        steps = self.doctor._next_steps(checks, offline=False)
        storage_step = next(step for step in steps if "storage.objects.get" in step)
        self.assertIn("storage.objects.create", storage_step)
        self.assertIn("storage.objects.delete", storage_step)
        self.assertIn("roles/storage.objectUser", storage_step)
        self.assertIn("not required", storage_step)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
SMOKE = ROOT / "scripts" / "gemini_acceptance_smoke.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("stageguard_gemini_acceptance_smoke_test_module", SMOKE)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load gemini_acceptance_smoke.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class GeminiAcceptanceSmokeCliTests(unittest.TestCase):
    def _run(self, *args: str, env_overrides: dict[str, str | None] | None = None) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        for name in ("GOOGLE_CLOUD_PROJECT", "GOOGLE_CLOUD_LOCATION", "STAGEGUARD_GEMINI_MODEL"):
            env.pop(name, None)
        env["GOOGLE_CLOUD_PROJECT"] = "stageguard-test"
        for name, value in (env_overrides or {}).items():
            if value is None:
                env.pop(name, None)
            else:
                env[name] = value
        return subprocess.run(
            [sys.executable, str(SMOKE), "--json", *args],
            cwd=ROOT,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=20,
        )

    def test_default_is_validation_only_and_never_executes_model(self) -> None:
        result = self._run()
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "validated")
        self.assertEqual(payload["request_count"], 0)
        self.assertIs(payload["state_mutation"], False)
        self.assertIs(payload["plan"]["execute"], False)
        self.assertEqual(payload["plan"]["location"], "global")
        self.assertEqual(payload["plan"]["model"], "gemini-2.5-flash")

    def test_missing_project_fails_before_any_live_request(self) -> None:
        result = self._run(env_overrides={"GOOGLE_CLOUD_PROJECT": None})
        self.assertEqual(result.returncode, 2)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "invalid")
        self.assertIn("GOOGLE_CLOUD_PROJECT", payload["error"])

    def test_project_number_and_resource_path_are_rejected(self) -> None:
        for project in ("123456789012", "projects/stageguard-test", "https://example.invalid/project"):
            with self.subTest(project=project):
                result = self._run("--project", project)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(json.loads(result.stdout)["status"], "invalid")

    def test_location_and_model_reject_resource_paths(self) -> None:
        result = self._run(
            "--location",
            "projects/stageguard-test/locations/global",
            "--model",
            "publishers/google/models/gemini-2.5-flash",
        )
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stdout)["status"], "invalid")


class GeminiAcceptanceSmokeUnitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.smoke = _load_module()

    def test_execute_is_explicitly_opt_in(self) -> None:
        args = argparse.Namespace(project="stageguard-test", location=None, model=None, execute=False)
        with mock.patch.dict(os.environ, {}, clear=True):
            plan = self.smoke._resolve_plan(args)
        self.assertFalse(plan.execute)

    def test_main_does_not_call_executor_without_execute_flag(self) -> None:
        with mock.patch.dict(os.environ, {"GOOGLE_CLOUD_PROJECT": "stageguard-test"}, clear=True), mock.patch.object(
            self.smoke, "_execute_smoke"
        ) as execute:
            code = self.smoke.main(["--json"])
        self.assertEqual(code, 0)
        execute.assert_not_called()

    def test_execute_path_calls_executor_exactly_once(self) -> None:
        live_result = {
            "status": "ok",
            "purpose": "stageguard-gemini-acceptance",
            "request_count": 1,
            "state_mutation": False,
        }
        with mock.patch.dict(os.environ, {"GOOGLE_CLOUD_PROJECT": "stageguard-test"}, clear=True), mock.patch.object(
            self.smoke, "_execute_smoke", return_value=live_result
        ) as execute, mock.patch("builtins.print"):
            code = self.smoke.main(["--execute", "--json"])
        self.assertEqual(code, 0)
        execute.assert_called_once()
        plan = execute.call_args.args[0]
        self.assertTrue(plan.execute)
        self.assertEqual(plan.project, "stageguard-test")
        self.assertEqual(plan.location, "global")
        self.assertEqual(plan.model, "gemini-2.5-flash")

    def test_pre_request_failure_reports_zero_requests_and_safe_error(self) -> None:
        failure = self.smoke.SmokeExecutionError(
            "dependency_missing",
            "install google-genai to run the live Gemini acceptance smoke test",
            request_started=False,
        )
        with mock.patch.dict(os.environ, {"GOOGLE_CLOUD_PROJECT": "stageguard-test"}, clear=True), mock.patch.object(
            self.smoke, "_execute_smoke", side_effect=failure
        ), mock.patch("builtins.print") as output:
            code = self.smoke.main(["--execute", "--json"])
        self.assertEqual(code, 1)
        payload = json.loads(output.call_args.args[0])
        self.assertEqual(payload["request_count"], 0)
        self.assertEqual(payload["error_code"], "dependency_missing")
        self.assertNotIn("token", payload["error"].lower())

    def test_request_failure_reports_one_attempt_without_provider_exception_text(self) -> None:
        failure = self.smoke.SmokeExecutionError(
            "generate_content_failed",
            "Gemini generateContent failed; verify ADC, Vertex AI API, model/location, quota, and runtime IAM",
            request_started=True,
        )
        with mock.patch.dict(os.environ, {"GOOGLE_CLOUD_PROJECT": "stageguard-test"}, clear=True), mock.patch.object(
            self.smoke, "_execute_smoke", side_effect=failure
        ), mock.patch("builtins.print") as output:
            code = self.smoke.main(["--execute", "--json"])
        self.assertEqual(code, 1)
        payload = json.loads(output.call_args.args[0])
        self.assertEqual(payload["request_count"], 1)
        self.assertEqual(payload["error_code"], "generate_content_failed")
        self.assertNotIn("synthetic-secret", payload["error"])

    def test_live_result_contract_is_state_isolated(self) -> None:
        self.assertNotIn("incident", self.smoke._execute_smoke.__doc__.lower())
        source = SMOKE.read_text(encoding="utf-8")
        self.assertIn('"request_count": 1', source)
        self.assertIn('"state_mutation": False', source)
        self.assertNotIn("remediation_url", source)
        self.assertNotIn("GRAFANA_TOKEN", source)


if __name__ == "__main__":
    unittest.main()

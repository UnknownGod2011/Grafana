from __future__ import annotations
import argparse, importlib.util, io, subprocess, sys, tempfile, unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest import mock
ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "scripts" / "run_stageguard_validation.py"
_spec = importlib.util.spec_from_file_location("stageguard_validation_runner", RUNNER)
assert _spec is not None and _spec.loader is not None
runner = importlib.util.module_from_spec(_spec); sys.modules[_spec.name] = runner; _spec.loader.exec_module(runner)

class StageGuardValidationRunnerTests(unittest.TestCase):
    def test_every_gate_resolves_to_concrete_tests(self):
        for gate in runner.GATES:
            with self.subTest(gate=gate.name): self.assertTrue(runner._files(gate))
    def test_validation_harness_gate_owns_runner_regressions(self):
        harness=next(g for g in runner.GATES if g.name=="validation harness")
        names={p.name for p in runner._files(harness)}
        self.assertIn("test_stageguard_validation_runner.py", names)
        self.assertTrue(any(name.startswith("test_validation_") for name in names))
        self.assertTrue(all(name=="test_stageguard_validation_runner.py" or name.startswith("test_validation_") for name in names))
    def test_runtime_activation_gate_covers_configuration_to_runtime_boundary(self):
        gate=next(g for g in runner.GATES if g.name=="runtime activation")
        self.assertEqual({p.name for p in runner._files(gate)}, {"test_activation.py"})
    def test_operator_api_boundary_covers_auth_framing_and_protocol_contracts(self):
        gate=next(g for g in runner.GATES if g.name=="operator API boundary"); names={p.name for p in runner._files(gate)}
        required={"test_api.py","test_api_auth_error_redaction.py","test_api_protocol_preflight.py","test_api_request_framing.py","test_http_surface_contract.py","test_identity.py"}; self.assertEqual(names,required)
    def test_operator_concurrency_gate_covers_responsiveness_and_execution_watchdog(self):
        gate=next(g for g in runner.GATES if g.name=="operator concurrency")
        self.assertEqual({p.name for p in runner._files(gate)}, {"test_api_concurrency.py","test_api_execution_watchdog.py"})
    def test_incident_lifecycle_gate_covers_fail_closed_and_recovery_contracts(self):
        gate=next(g for g in runner.GATES if g.name=="incident lifecycle"); names={p.name for p in runner._files(gate)}
        required={"test_anchored_incident_runtime.py","test_anchored_recovery_recheck.py","test_api_recovery_recheck.py","test_api_evidence_unavailable_briefing.py","test_api_evidence_unavailable_mutations.py","test_anchored_transition_failure_authority.py"}; self.assertTrue(required.issubset(names), required-names)
    def test_timeline_gate_includes_audit_timeline_contracts(self):
        gate=next(g for g in runner.GATES if g.name=="timeline disclosure"); names={p.name for p in runner._files(gate)}
        for name in ("test_timeline_projection.py","test_audit_timeline.py","test_audit_timeline_reconciliation_projection.py"): self.assertIn(name,names)
    def test_file_selection_is_unique_and_deterministic(self):
        for gate in runner.GATES:
            names=[p.name for p in runner._files(gate)]; self.assertEqual(names,sorted(set(names)))
    def test_execution_plan_runs_each_test_at_most_once(self):
        shared=runner.TESTS/"test_shared.py"; unique=runner.TESTS/"test_unique.py"; first=runner.Gate("first",("unused",)); second=runner.Gate("second",("unused",))
        plan=runner._execution_plan(((first,(shared,unique)),(second,(shared,))))
        self.assertEqual(plan[0],(first,(shared,unique),())); self.assertEqual(plan[1],(second,(),(shared,)))
        self.assertEqual([p.name for _,files,_ in plan for p in files],["test_shared.py","test_unique.py"])
    def test_unowned_tests_report_only_safe_runtime_tests(self):
        with tempfile.TemporaryDirectory() as d:
            tests=Path(d); owned=tests/"test_owned.py"; unowned=tests/"test_unowned.py"; ignored=tests/"helper.py"
            for p in (owned,unowned,ignored): p.write_text("pass\n")
            with mock.patch.object(runner,"TESTS",tests):
                selections=((runner.Gate("synthetic",("test_owned.py",)),(owned,)),)
                self.assertEqual([p.name for p in runner._unowned_tests(selections)],["test_unowned.py"])
    def test_require_full_coverage_fails_closed_on_unowned_test(self):
        gate=runner.Gate("synthetic",("test_timeline_projection.py",)); err=io.StringIO()
        with mock.patch.object(runner,"GATES",(gate,)), mock.patch.object(runner,"_unowned_tests",return_value=(runner.TESTS/"test_unowned.py",)), mock.patch.object(sys,"argv",["run_stageguard_validation.py","--require-full-coverage"]), redirect_stderr(err):
            self.assertEqual(runner.main(),2)
        self.assertIn("test_unowned.py",err.getvalue())
    def test_commands_are_scoped_to_one_concrete_file(self):
        command=runner._command(runner.TESTS/"test_timeline_projection.py"); self.assertEqual(command[-2:],["-p","test_timeline_projection.py"]); self.assertNotIn("-t",command)
    def test_command_rejects_paths_outside_test_directory(self):
        with tempfile.TemporaryDirectory() as d:
            outside=Path(d)/"test_timeline_projection.py"; outside.write_text("pass\n")
            with self.assertRaises(ValueError): runner._command(outside)
    def test_safe_test_file_rejects_symlink(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); tests=root/"tests"; tests.mkdir(); target=root/"outside.py"; target.write_text("pass\n"); link=tests/"test_link.py"
            try: link.symlink_to(target)
            except (OSError,NotImplementedError): self.skipTest("symlinks unavailable")
            with mock.patch.object(runner,"TESTS",tests): self.assertFalse(runner._safe_test_file(link))
    def test_safe_test_file_accepts_direct_regular_file(self):
        with tempfile.TemporaryDirectory() as d:
            tests=Path(d)/"tests"; tests.mkdir(); f=tests/"test_ok.py"; f.write_text("pass\n")
            with mock.patch.object(runner,"TESTS",tests): self.assertTrue(runner._safe_test_file(f))
    def test_validation_environment_scrubs_live_integration_credentials(self):
        source={"PATH":"/usr/bin","HOME":"/tmp/home","GRAFANA_TOKEN":"x","GEMINI_API_KEY":"x","GOOGLE_API_KEY":"x","GOOGLE_APPLICATION_CREDENTIALS":"x","GOOGLE_CREDENTIALS":"{\"private_key\":\"x\"}","GOOGLE_CLOUD_KEYFILE_JSON":"{\"private_key\":\"x\"}","CLOUDSDK_AUTH_ACCESS_TOKEN":"x","STAGEGUARD_REMEDIATION_TOKEN":"x","SOME_OTHER_TOKEN":"x","APP_PASSWORD":"x","ORDINARY_SETTING":"safe"}; sanitized=runner._validation_env(source); self.assertEqual(sanitized["ORDINARY_SETTING"],"safe")
        for n in set(source)-{"PATH","HOME","ORDINARY_SETTING"}: self.assertNotIn(n,sanitized)
    def test_validation_environment_scrubs_python_code_injection_controls(self):
        source={"PATH":"/usr/bin","PYTHONPATH":"x","PYTHONHOME":"x","PYTHONSTARTUP":"x","PYTHONINSPECT":"1","PYTHONBREAKPOINT":"x","PYTHONUNBUFFERED":"1"}; s=runner._validation_env(source)
        for n in ("PYTHONPATH","PYTHONHOME","PYTHONSTARTUP","PYTHONINSPECT","PYTHONBREAKPOINT"): self.assertNotIn(n,s)
        self.assertEqual(s["PYTHONUNBUFFERED"],"1")
    def test_validation_environment_disables_user_site_and_bytecode_writes(self):
        s=runner._validation_env({"PATH":"/usr/bin","PYTHONNOUSERSITE":"0","PYTHONDONTWRITEBYTECODE":"0"}); self.assertEqual(s["PYTHONNOUSERSITE"],"1"); self.assertEqual(s["PYTHONDONTWRITEBYTECODE"],"1")
    def test_validation_environment_blocks_ambient_gce_metadata_credentials(self):
        source={"PATH":"/usr/bin","GCE_METADATA_HOST":"metadata.google.internal","GCE_METADATA_IP":"169.254.169.254","ORDINARY_SETTING":"safe"}
        s=runner._validation_env(source)
        self.assertEqual(s["GCE_METADATA_HOST"],"127.0.0.1:9")
        self.assertEqual(s["GCE_METADATA_IP"],"127.0.0.1")
        self.assertEqual(s["ORDINARY_SETTING"],"safe")
        self.assertNotIn("metadata.google.internal",s.values()); self.assertNotIn("169.254.169.254",s.values())
    def test_validation_environment_disables_ambient_aws_metadata_credentials(self):
        source={"PATH":"/usr/bin","AWS_EC2_METADATA_DISABLED":"false","AWS_PROFILE":"production","AWS_ACCESS_KEY_ID":"secret","ORDINARY_SETTING":"safe"}
        s=runner._validation_env(source)
        self.assertEqual(s["AWS_EC2_METADATA_DISABLED"],"true")
        self.assertNotIn("AWS_PROFILE",s); self.assertNotIn("AWS_ACCESS_KEY_ID",s)
        self.assertEqual(s["ORDINARY_SETTING"],"safe")
    def test_validation_environment_drops_proxy_urls_and_credentials(self):
        source={"PATH":"/usr/bin","HTTP_PROXY":"http://alice:secret@proxy.example:8080","https_proxy":"https://bob:token@proxy.example:8443","ALL_PROXY":"socks5://proxy.example:1080","no_proxy":"metadata.google.internal","ORDINARY_SETTING":"safe"}
        s=runner._validation_env(source)
        for name in ("HTTP_PROXY","https_proxy","ALL_PROXY","no_proxy"): self.assertNotIn(name,s)
        self.assertEqual(s["NO_PROXY"],"localhost,127.0.0.1,::1")
        self.assertEqual(s["ORDINARY_SETTING"],"safe")
        self.assertFalse(any("secret" in value or "token@" in value or "proxy.example" in value for value in s.values()))
    def test_validation_environment_isolates_well_known_google_adc_locations(self):
        source={"PATH":"/usr/bin","HOME":"/real/home","USERPROFILE":"C:/Users/real","CLOUDSDK_CONFIG":"/real/gcloud","ORDINARY_SETTING":"safe"}
        s=runner._validation_env(source,isolated_home="/tmp/stageguard-isolated")
        self.assertEqual(s["HOME"],"/tmp/stageguard-isolated")
        self.assertEqual(s["USERPROFILE"],"/tmp/stageguard-isolated")
        self.assertEqual(s["CLOUDSDK_CONFIG"],str(Path("/tmp/stageguard-isolated")/".config"/"gcloud"))
        self.assertEqual(s["ORDINARY_SETTING"],"safe")
        self.assertNotIn("/real/home",s.values()); self.assertNotIn("C:/Users/real",s.values()); self.assertNotIn("/real/gcloud",s.values())
    def test_validation_environment_does_not_mutate_source(self):
        source={"GRAFANA_TOKEN":"secret","SAFE":"value"}; original=dict(source); sanitized=runner._validation_env(source); self.assertEqual(source,original); self.assertIsNot(sanitized,source)
    def test_sensitive_environment_matching_is_case_insensitive(self):
        for n in ("grafana_token","Gemini_Api_Key","my_secret","foo_PASSWORD","pythonpath","PythonStartup","google_credentials","Google_Cloud_Keyfile_Json","gce_metadata_host","Gce_Metadata_Ip","http_proxy","Https_Proxy","all_proxy","No_Proxy"): self.assertTrue(runner._is_sensitive_env_name(n))
    def test_test_file_subprocess_has_no_interactive_stdin(self):
        path=runner.TESTS/"test_timeline_projection.py"; env={"PATH":"/usr/bin"}; completed=mock.Mock(returncode=0)
        with mock.patch.object(subprocess,"run",return_value=completed) as run: self.assertEqual(runner._run_test_file(path,timeout=5.0,env=env),0)
        kwargs=run.call_args.kwargs; self.assertIs(kwargs["stdin"],subprocess.DEVNULL); self.assertEqual(kwargs["timeout"],5.0); self.assertIs(kwargs["env"],env); self.assertFalse(kwargs["check"]); self.assertEqual(kwargs["cwd"],runner.ROOT)
    def test_main_classifies_subprocess_launch_error_as_validation_failure(self):
        gate=runner.Gate("synthetic",("test_timeline_projection.py",)); err=io.StringIO()
        with mock.patch.object(runner,"GATES",(gate,)), mock.patch.object(runner,"_run_test_file",side_effect=OSError("interpreter unavailable")), mock.patch.object(sys,"argv",["run_stageguard_validation.py"]), redirect_stderr(err):
            self.assertEqual(runner.main(),1)
        output=err.getvalue(); self.assertIn("LAUNCH ERROR: test_timeline_projection.py",output); self.assertIn("synthetic/test_timeline_projection.py",output)
    def test_default_file_timeout_is_bounded(self):
        self.assertGreater(runner.DEFAULT_FILE_TIMEOUT_SECONDS,0); self.assertLessEqual(runner.DEFAULT_FILE_TIMEOUT_SECONDS,300); self.assertLessEqual(runner.DEFAULT_FILE_TIMEOUT_SECONDS,runner.MAX_FILE_TIMEOUT_SECONDS)
    def test_timeout_parser_rejects_unbounded_non_positive_or_excessive_values(self):
        for value in ("0","-1","nan","inf","-inf",str(runner.MAX_FILE_TIMEOUT_SECONDS+1),"1e308"):
            with self.assertRaises(argparse.ArgumentTypeError): runner._positive_timeout(value)
    def test_timeout_parser_accepts_fractional_seconds_and_maximum(self):
        self.assertEqual(runner._positive_timeout("2.5"),2.5); self.assertEqual(runner._positive_timeout(str(runner.MAX_FILE_TIMEOUT_SECONDS)),runner.MAX_FILE_TIMEOUT_SECONDS)

if __name__ == "__main__": unittest.main()

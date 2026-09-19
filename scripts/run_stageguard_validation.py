#!/usr/bin/env python3
"""Run StageGuard's dependency-light production safety and Grafana/MCP gates."""
from __future__ import annotations
import argparse, math, os, subprocess, sys, tempfile
from dataclasses import dataclass
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; TESTS=ROOT/"runtime"/"tests"
DEFAULT_FILE_TIMEOUT_SECONDS=120.0; MAX_FILE_TIMEOUT_SECONDS=3600.0
SENSITIVE_ENV_NAMES=frozenset({"GOOGLE_APPLICATION_CREDENTIALS","GOOGLE_CREDENTIALS","GOOGLE_CLOUD_KEYFILE_JSON","CLOUDSDK_AUTH_ACCESS_TOKEN","CLOUDSDK_AUTH_CREDENTIAL_FILE_OVERRIDE","CLOUDSDK_CONFIG","GCE_METADATA_HOST","GCE_METADATA_IP","HOME","USERPROFILE","TMPDIR","TMP","TEMP","HTTP_PROXY","HTTPS_PROXY","ALL_PROXY","NO_PROXY","PYTHONHOME","PYTHONPATH","PYTHONSTARTUP","PYTHONINSPECT","PYTHONBREAKPOINT","PYTHONWARNINGS","PYTHONUSERBASE","PYTHONPYCACHEPREFIX","PYTHONEXECUTABLE","SSH_AUTH_SOCK","SSH_AGENT_PID","GIT_ASKPASS","SSH_ASKPASS","GIT_SSH","GIT_SSH_COMMAND","NETRC","DOCKER_CONFIG","KUBECONFIG","PIP_INDEX_URL","PIP_EXTRA_INDEX_URL","PIP_CONFIG_FILE","NPM_CONFIG_USERCONFIG","YARN_RC_FILENAME","CURL_HOME","WGETRC","XDG_CONFIG_HOME","XDG_DATA_HOME","APPDATA","LOCALAPPDATA","SSLKEYLOGFILE","SSL_CERT_FILE","SSL_CERT_DIR","REQUESTS_CA_BUNDLE","CURL_CA_BUNDLE","LD_PRELOAD","LD_LIBRARY_PATH","BASH_ENV","ENV","ZDOTDIR","NODE_OPTIONS","NODE_PATH","RUBYOPT","RUBYLIB","PERL5OPT","PERL5LIB","JAVA_TOOL_OPTIONS","JDK_JAVA_OPTIONS","CLASSPATH","MAVEN_OPTS","MAVEN_ARGS","MAVEN_USER_HOME","GRADLE_OPTS","GRADLE_USER_HOME","DOTNET_STARTUP_HOOKS","DOTNET_ADDITIONAL_DEPS","DOTNET_SHARED_STORE","CORECLR_PROFILER","CORECLR_PROFILER_PATH","CORECLR_ENABLE_PROFILING","GOENV","GOFLAGS","GOTOOLCHAIN","GOWORK","CARGO_HOME","RUSTC_WRAPPER","RUSTC_WORKSPACE_WRAPPER","RUSTFLAGS","RUSTDOCFLAGS"})
SENSITIVE_ENV_PREFIXES=("GRAFANA_","GEMINI_","GOOGLE_API_","STAGEGUARD_REMEDIATION_","AWS_","AZURE_","ANTHROPIC_","OPENAI_","GITHUB_","GH_","HF_","HUGGINGFACE_","GIT_CONFIG_","DYLD_")
SENSITIVE_ENV_SUFFIXES=("_TOKEN","_AUTH_TOKEN","_BEARER_TOKEN","_API_KEY","_PASSWORD","_SECRET","_ACCESS_KEY","_PRIVATE_KEY","_CLIENT_SECRET","_CREDENTIAL","_CREDENTIALS")
VALIDATION_ENV_OVERRIDES={"PYTHONNOUSERSITE":"1","PYTHONDONTWRITEBYTECODE":"1","GCE_METADATA_HOST":"127.0.0.1:9","GCE_METADATA_IP":"127.0.0.1","AWS_EC2_METADATA_DISABLED":"true","NO_PROXY":"localhost,127.0.0.1,::1","GIT_TERMINAL_PROMPT":"0","PIP_NO_INPUT":"1"}
@dataclass(frozen=True)
class Gate: name:str; patterns:tuple[str,...]
GATES=(Gate("validation harness",("test_stageguard_validation_runner.py","test_validation_*.py")),Gate("runtime activation",("test_activation.py",)),Gate("telemetry simulator",("test_simulator.py",)),Gate("durable state integrity",("test_*checkpoint*.py","test_*integrity*.py","test_*file_lock*.py","test_validation_durable_state_integrity.py")),Gate("cloud durability simulation",("test_gcs_checkpoint.py","test_gcs_multiprocess_cas.py","test_fake_cloud_restart_acceptance.py")),Gate("retention safety",("test_retention_planner.py","test_retention_executor.py","test_retention_path_security.py","test_retention_coordinator_cli.py")),Gate("evidence and diagnosis",("test_telemetry.py","test_log_activation.py","test_log_evidence.py","test_investigator.py","test_correlated_investigator.py","test_briefing_runtime.py","test_gemini_commander.py","test_gemini_acceptance_smoke.py")),Gate("operator readiness and UI",("test_bootstrap.py","test_incident_service.py","test_onboarding.py","test_readiness*.py","test_operator_*.py","test_preflight_cli.py","test_stageguard_doctor.py","test_command_line*.py")),Gate("operator API boundary",("test_api.py","test_api_auth_error_redaction.py","test_api_protocol_preflight.py","test_api_request_framing.py","test_http_surface_contract.py","test_identity.py")),Gate("operator concurrency",("test_api_concurrency.py","test_api_execution_watchdog.py")),Gate("incident lifecycle",("test_anchored_incident_runtime.py","test_*evidence_unavailable*.py","test_*recovery_recheck.py","test_recovery_recheck_restart.py","test_*transition_failure_authority.py","test_transition_failure_snapshot_authority.py")),Gate("remediation adapter boundary",("test_remediation.py","test_remediation_receiver.py","test_remediation_result_boundary.py","test_production_remediation.py","test_http_remediation_transport.py","test_http_remediation_tls_integration.py","test_http_reconciliation_audit_sequence.py","test_http_subprocess_*.py","test_production_reconciliation_bootstrap.py","test_validation_remediation_boundary.py")),Gate("cloud deployment contract",("test_cloud_run_deploy_contract.py","test_cloud_run_deploy_shell.py","test_deploy_cloud_run_script.py","test_cloudrun_entrypoint.py")),Gate("GCP deployment readiness",("test_gcp_deploy_doctor.py","test_gcp_deploy_doctor_fake_gcloud.py","test_gcp_deploy_doctor_process_failures.py","test_gcp_deploy_doctor_serialization.py","test_gcp_identifiers.py")),Gate("cloud runtime metrics bridge",("test_cloud_run_metrics_bridge.py","test_cloud_run_metrics_acceptance.py","test_cloud_run_metrics_bridge_audience_boundary.py","test_cloud_run_metrics_bridge_bounds.py","test_cloud_run_metrics_bridge_inbound_auth.py","test_cloud_run_metrics_bridge_redirects.py","test_cloud_run_metrics_bridge_sentinel_family.py")),Gate("runtime observability",("test_grafana_runtime_observability.py","test_recovery_observability.py","test_watchdog_*.py","test_observability_image_pins.py")),Gate("timeline disclosure",("test_timeline*.py","test_audit_timeline*.py")),Gate("public audit",("test_*audit*.py",)),Gate("execution concurrency simulation",("test_execution_gcs_multiprocess_cas.py","test_execution_reconciliation_gcs_multiprocess_cas.py")),Gate("execution safety",("test_anchored_execution_safety.py","test_bootstrap_execution_safety.py","test_execution_conflict_reload_phases.py","test_execution_crash_matrix.py","test_execution_outcome_checkpoint_authority.py","test_execution_phase_observability.py","test_execution_phase_v2.py","test_execution_reconciliation_audit.py","test_execution_reconciliation_gate.py","test_execution_reconciliation_observability.py","test_execution_safety.py","test_execution_safety_api.py","test_execution_safety_http_transport.py","test_execution_watchdog_bounds.py","test_execution_watchdog_clock_boundary.py","test_local_execution_uncertainty_barrier.py","test_subprocess_crash_recovery.py")),Gate("Grafana MCP",("test_*mcp*.py",)),)
def _safe_test_file(path):
 try:return path.parent.resolve(strict=True)==TESTS.resolve(strict=True) and not path.is_symlink() and path.is_file()
 except (OSError,RuntimeError):return False
def _files(gate):
 selected={}
 for pattern in gate.patterns:
  for path in TESTS.glob(pattern):
   if _safe_test_file(path):selected[path.name]=path
 return tuple(selected[n] for n in sorted(selected))
def _all_safe_tests():return tuple(sorted((p for p in TESTS.glob("test_*.py") if _safe_test_file(p)),key=lambda p:p.name))
def _unowned_tests(selections):
 owned={p.name for _,files in selections for p in files};return tuple(p for p in _all_safe_tests() if p.name not in owned)
def _execution_plan(selections):
 seen=set();plan=[]
 for gate,files in selections:
  runnable=tuple(p for p in files if p.name not in seen);covered=tuple(p for p in files if p.name in seen);seen.update(p.name for p in files);plan.append((gate,runnable,covered))
 return tuple(plan)
def _command(path):
 if not _safe_test_file(path):raise ValueError(f"unsafe validation test path: {path}")
 return [sys.executable,"-m","unittest","discover","-s",str(TESTS),"-p",path.name]
def _is_sensitive_env_name(name):
 upper=name.upper();return upper in SENSITIVE_ENV_NAMES or upper.startswith(SENSITIVE_ENV_PREFIXES) or upper.endswith(SENSITIVE_ENV_SUFFIXES)
def _validation_env(source=None,*,isolated_home=None):
 source_env=os.environ if source is None else source;sanitized={k:v for k,v in source_env.items() if not _is_sensitive_env_name(k)};sanitized.update(VALIDATION_ENV_OVERRIDES)
 if isolated_home is not None:
  home=Path(isolated_home); temp=home/"tmp"; temp.mkdir(mode=0o700,parents=True,exist_ok=True)
  sanitized["HOME"]=str(home);sanitized["USERPROFILE"]=str(home);sanitized["TMPDIR"]=str(temp);sanitized["TMP"]=str(temp);sanitized["TEMP"]=str(temp);sanitized["XDG_CONFIG_HOME"]=str(home/".config");sanitized["XDG_DATA_HOME"]=str(home/".local"/"share");sanitized["APPDATA"]=str(home/"AppData"/"Roaming");sanitized["LOCALAPPDATA"]=str(home/"AppData"/"Local");sanitized["CLOUDSDK_CONFIG"]=str(home/".config"/"gcloud")
 return sanitized
def _positive_timeout(value):
 try:timeout=float(value)
 except ValueError as exc:raise argparse.ArgumentTypeError("timeout must be a number") from exc
 if not math.isfinite(timeout) or timeout<=0:raise argparse.ArgumentTypeError("timeout must be a finite number greater than zero")
 if timeout>MAX_FILE_TIMEOUT_SECONDS:raise argparse.ArgumentTypeError(f"timeout must not exceed {MAX_FILE_TIMEOUT_SECONDS:g} seconds")
 return timeout
def _run_test_file(path,*,timeout,env):return subprocess.run(_command(path),cwd=ROOT,check=False,timeout=timeout,env=env,stdin=subprocess.DEVNULL).returncode
def main():
 parser=argparse.ArgumentParser(description="Run dependency-light StageGuard safety/MCP regression gates.");parser.add_argument("--keep-going",action="store_true");parser.add_argument("--list",action="store_true");parser.add_argument("--require-full-coverage",action="store_true",help="fail if any safe runtime test is not owned by a production validation gate");parser.add_argument("--file-timeout",type=_positive_timeout,default=DEFAULT_FILE_TIMEOUT_SECONDS,metavar="SECONDS");args=parser.parse_args()
 if not TESTS.is_dir() or TESTS.is_symlink():print(f"error: safe test directory not found: {TESTS}",file=sys.stderr);return 2
 selections=tuple((g,_files(g)) for g in GATES);empty=[g.name for g,f in selections if not f]
 if empty:print("error: validation gate matched no safe tests: "+", ".join(empty),file=sys.stderr);return 2
 unowned=_unowned_tests(selections)
 if args.require_full_coverage and unowned:print("error: safe runtime tests are not owned by validation gates: "+", ".join(p.name for p in unowned),file=sys.stderr);return 2
 plan=_execution_plan(selections)
 if args.list:
  for gate,runnable,covered in plan:
   print(f"{gate.name} ({', '.join(gate.patterns)}):")
   for path in runnable:print(f"  {path.relative_to(ROOT)}")
   for path in covered:print(f"  {path.relative_to(ROOT)} [covered by earlier gate]")
  if unowned:
   print("unowned safe runtime tests:")
   for path in unowned:print(f"  {path.relative_to(ROOT)}")
  return 0
 failures=[]
 with tempfile.TemporaryDirectory(prefix="stageguard-validation-") as isolated_home:
  env=_validation_env(isolated_home=isolated_home)
  for gate,files,covered in plan:
   print(f"\n=== StageGuard gate: {gate.name} ({len(files)} files; {len(covered)} already covered) ===",flush=True);gate_failed=False
   for path in files:
    print(f"--- {path.name} ---",flush=True)
    try:failed=_run_test_file(path,timeout=args.file_timeout,env=env)!=0
    except subprocess.TimeoutExpired:failed=True;print(f"TIMEOUT: {path.name} exceeded {args.file_timeout:g}s",file=sys.stderr)
    except OSError as exc:failed=True;print(f"LAUNCH ERROR: {path.name}: {type(exc).__name__}: {exc}",file=sys.stderr)
    if failed:
     gate_failed=True;failures.append(f"{gate.name}/{path.name}")
     if not args.keep_going:break
   if gate_failed and not args.keep_going:break
 if failures:print("\nFAILED tests: "+", ".join(failures),file=sys.stderr);return 1
 print("\nAll selected StageGuard validation gates passed.");print("Live Docker/Grafana MCP smoke is intentionally not part of this runner.");return 0
if __name__=="__main__":raise SystemExit(main())

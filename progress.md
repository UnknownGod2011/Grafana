# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the indispensable runtime evidence plane. The working vertical slice remains: deterministic telemetry, Prometheus/Loki/Grafana, official read-only Grafana MCP access, bounded diagnosis, optional revision-bound Gemini briefing, exact human approval, safe remediation, Grafana-based recovery verification, authenticated lifecycle state, restart reconciliation, and a same-origin operator cockpit.

Core invariants:
- Grafana is the evidence plane; infrastructure write credentials stay isolated from Grafana/MCP access.
- Gemini is optional/advisory and cannot mutate diagnosis, approval, remediation, or recovery state.
- Human approval is single-use and bound to the exact evidence revision.
- Remediation success is never inferred from an action response; fresh Grafana telemetry must prove recovery.
- Authenticated checkpoints and audit integrity fail closed.

## Run log — 2026-09-10 — end-to-end fake-gcloud deployment doctor

### Inspected at start

Read `progress.md` completely before choosing work. Inspected the repository root and the current Google Cloud deployment-preflight boundary, especially:
- `scripts/gcp_deploy_doctor.py`
- `runtime/tests/test_gcp_deploy_doctor.py`
- current repository root/documentation layout

The previous handoff identified the right next gap: the live Cloud Run region check had unit coverage, but there was no subprocess-level proof that the complete deployment doctor could traverse its real `gcloud` command sequence and derive `ready_to_deploy` correctly without real Google Cloud credentials.

### Exact changes made

1. Added `runtime/tests/test_gcp_deploy_doctor_fake_gcloud.py`.
   - Runs the actual `scripts/gcp_deploy_doctor.py --json` entrypoint as a subprocess.
   - Installs a temporary executable `gcloud` shim at the front of `PATH`; no real Google Cloud CLI, account, project, API, IAM policy, secret, bucket, image, or Cloud Run service is required.
   - Records every fake-gcloud invocation as JSONL so command families can be asserted after the doctor exits.
   - Simulates active authentication, project-number resolution, Cloud Run region catalog, enabled APIs, secret existence, IAM Policy Troubleshooter, checkpoint bucket existence, and Artifact Registry image existence.

2. Added behavioral coverage proving:
   - a supported Cloud Run region can complete the full read-only preflight and produce `ready_to_deploy=true` when every simulated dependency and permission is healthy;
   - an unsupported region forces exit code 2 and `ready_to_deploy=false` while the doctor still collects the remaining API/storage/IAM/image evidence instead of prematurely hiding additional failures;
   - an empty provider region catalog fails closed;
   - denying exactly `storage.objects.delete` keeps deploy readiness false while `storage.objects.get` and `storage.objects.create` remain independently successful;
   - the complete healthy non-Gemini path issues 10 Policy Troubleshooter calls: five Secret Manager permissions, three checkpoint-object permissions, and two Cloud Logging permissions.

3. Simplified the fake Policy Troubleshooter dispatcher after re-reading the committed harness so its command match is explicit and maintainable.

Commits:
- `7f53b231027ab8f4581f344d5e8ae9e2b108e620` — initial end-to-end fake-gcloud deployment-doctor harness
- `97a288b4ac3fcfbdf5e98c81099944e6b39e48a6` — clean imports and simplify fake Policy Troubleshooter dispatch

### Tests / checks / results

Attempted the exact focused suite from a clean checkout:

`python -m unittest runtime.tests.test_gcp_deploy_doctor_fake_gcloud runtime.tests.test_gcp_deploy_doctor`

The execution container still cannot resolve `github.com`; `git clone --depth 1 https://github.com/UnknownGod2011/Grafana.git` failed with `Could not resolve host: github.com` before tests could execute. Therefore no committed-suite green claim is made.

Additional validation performed:
- re-fetched the newly committed harness through the GitHub connector and reviewed the final source;
- verified the fake command dispatcher covers every non-Gemini `gcloud` command family currently issued by `_gcloud_checks()`;
- verified the expected Policy Troubleshooter cardinality against the current doctor contract: 5 secret + 3 storage + 2 logging = 10;
- kept the test isolated to temporary files and subprocess environment overrides.

No GitHub Actions workflow was created, triggered, or rerun. No Grafana instance, MCP server, Google Cloud project, Cloud Run service, bucket/object, IAM policy, Secret Manager payload, Vertex/Gemini endpoint, or remediation endpoint was modified.

### Decisions made

1. Live-provider deployment preflight should have both unit-level checks and a credential-free subprocess contract test.
2. Unsupported region availability is a required failure, but the doctor should continue collecting other read-only deployment evidence so operators receive one useful diagnostic report rather than serial one-error-at-a-time failures.
3. Effective IAM permissions remain tested independently; losing one checkpoint permission must not blur the state of the other permissions.
4. The fake-gcloud harness is intentionally POSIX-only for now because the production deploy/operator path is shell-oriented; Windows continues to have unit-level Python doctor coverage.
5. No CI was enabled for this harness to avoid unnecessary Actions usage; it is designed for local/manual focused execution.

### Current blockers / unknowns

- The exact new fake-gcloud suite still needs execution from a runnable checkout because the current execution container cannot resolve GitHub.
- The full historical suite still needs systematic triage after repository execution is available.
- The exact Cloud Storage object Policy Troubleshooter tuple still needs one authorized disposable-project acceptance run.
- `ENABLE_GEMINI=true python scripts/gcp_deploy_doctor.py --json` still needs a live authorized disposable GCP project.
- `python scripts/gemini_acceptance_smoke.py --execute --json` still needs one real Vertex AI acceptance run after the doctor passes.
- `_run_gcloud()` currently relies directly on `subprocess.run(..., timeout=30)`. A true CLI hang/timeout or executable race can raise instead of being converted into a structured failed check; this is now the clearest fail-closed robustness gap in the deployment doctor.

## Single best next step

**Harden `scripts/gcp_deploy_doctor.py::_run_gcloud()` so `subprocess.TimeoutExpired` and executable/OS invocation failures become sanitized nonzero results rather than crashing the doctor, then extend the fake-gcloud/subprocess coverage to prove command timeout/failure yields structured `ready_to_deploy=false` JSON without leaking credentials or stack traces.**

## Retained production hardening

- Cloud Run production deployment uses authenticated GCS checkpoints rather than silent ephemeral/no-checkpoint state.
- Runtime checkpoint HMAC keys are Secret Manager supplied and at least 32 UTF-8 bytes.
- Checkpoint object validation is byte-accurate and aligned across deploy helper, deployment doctor, and runtime.
- Cloud Run deployment rejects malformed/injected comma-delimited environment and secret mapping inputs before `gcloud`.
- Google Cloud project/region/service/image identifier grammar is centralized and shared by the deploy helper and deployment doctor.
- Live deployment preflight verifies the configured Cloud Run region against the current provider-reported region catalog.
- Runtime MCP launcher parsing is centralized and cross-platform.
- Readiness validates local activation/pin trust before spawning/querying Grafana MCP.
- Deployment doctor validates required APIs, secrets/access, Cloud Logging permissions, checkpoint storage permissions, conditional Vertex prediction permission, image availability, live Cloud Run region availability, and deployment serialization boundaries; offline validation can never report deploy-ready.
- Gemini acceptance smoke defaults to zero model calls and requires explicit `--execute`.
- Standard Cloud Run deployment keeps production remediation disabled.

## Validation baseline retained

- Local onboarding doctor: 8 tests passed, 1 expected platform-specific permission test skipped on Windows.
- Focused core/API/UI suite from the last executable run: 81/81 passed.
- Historical full suite baseline: 352 tests, 9 failures, 15 errors, 19 skipped; no full-suite green claim.
- Live Docker rehearsal: PASS twice consecutively.
- Official Grafana MCP read-only smoke path: PASS using `grafana/mcp-grafana:1.3.0`.
- Incident flow: investigate -> diagnose `uplink-b packet loss` -> exact revision approval -> bounded remediation -> telemetry-verified recovered.

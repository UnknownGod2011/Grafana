# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the indispensable runtime evidence plane. The working vertical slice remains: deterministic telemetry, Prometheus/Loki/Grafana, official read-only Grafana MCP access, bounded diagnosis, optional revision-bound Gemini briefing, exact human approval, safe remediation, Grafana-based recovery verification, authenticated lifecycle state, restart reconciliation, and a same-origin operator cockpit.

Core invariants:
- Grafana is the evidence plane; infrastructure write credentials stay isolated from Grafana/MCP access.
- Gemini is optional/advisory and cannot mutate diagnosis, approval, remediation, or recovery state.
- Human approval is single-use and bound to the exact evidence revision.
- Remediation success is never inferred from an action response; fresh Grafana telemetry must prove recovery.
- Authenticated checkpoints and audit integrity fail closed.

## Run log — 2026-09-10 — fail-closed gcloud process boundary

### Inspected at start

Read `progress.md` completely before choosing work. Inspected the current repository state and the deployment-preflight surface, especially:
- `scripts/gcp_deploy_doctor.py`
- `scripts/gcp_identifiers.py`
- `runtime/tests/test_gcp_deploy_doctor.py`
- `runtime/tests/test_gcp_deploy_doctor_fake_gcloud.py`

The previous handoff identified `_run_gcloud()` as the highest-value robustness gap. Confirmed that it called `subprocess.run(..., timeout=30)` without catching process-layer exceptions, so a hung gcloud command, executable race/OS failure, or output decode failure could crash the deployment doctor before it emitted the promised structured fail-closed report.

### Exact changes made

1. Hardened `scripts/gcp_deploy_doctor.py::_run_gcloud()`.
   - Added named process-boundary constants: `GCLOUD_TIMEOUT_SECONDS=30`, timeout exit code `124`, and execution failure exit code `126`.
   - `subprocess.TimeoutExpired` is converted to `(124, "", "gcloud command timed out")`.
   - `OSError` and `UnicodeError` are converted to `(126, "", "gcloud command could not be executed")`.
   - Exception objects, command arguments, paths, secret identifiers, and raw subprocess stderr are not interpolated into those synthetic failure strings.
   - Existing callers therefore continue through their established nonzero-return fail-closed branches rather than losing the JSON report to an uncaught exception.

2. Added `runtime/tests/test_gcp_deploy_doctor_process_failures.py`.
   - Unit coverage injects `TimeoutExpired`, `FileNotFoundError`, and `UnicodeDecodeError` directly at the subprocess boundary.
   - Verifies timeout/OS/decode failures return stable sanitized codes/messages and do not echo a synthetic secret marker or private filesystem path.
   - Verifies `_gcloud_checks()` converts a runner timeout into a required failed `gcloud_auth` check rather than raising.
   - Adds a POSIX subprocess-level fake-`gcloud` case where the executable exits nonzero and writes synthetic stderr; the real doctor entrypoint must still emit parseable JSON, `ready_to_deploy=false`, exit 2, no traceback, and no forwarded fake-gcloud stderr.

Commits:
- `b14eb67c213f5fbcd57f172ae5087d0b177ce11e` — fail closed on gcloud invocation errors
- `1164300aa966b61f3c5cb2427de0de9d11da34eb` — cover sanitized gcloud process failures

### Tests / checks / results

Execution evidence available in this run:
- Exercised the exact new `_run_gcloud()` exception mapping logic in an isolated Python harness.
- Timeout case returned `(124, "", "gcloud command timed out")`.
- OS invocation failure returned `(126, "", "gcloud command could not be executed")`.
- Unicode decode failure returned `(126, "", "gcloud command could not be executed")`.
- Re-fetched and reviewed the committed regression test file after the GitHub write.

The full committed unittest modules were not executed from a repository checkout in this environment, so no new full-suite green claim is made. The retained historical execution baselines below remain the latest broader runnable evidence.

No GitHub Actions workflow was created, triggered, or rerun. No Grafana instance, MCP server, Google Cloud project, Cloud Run service, bucket/object, IAM policy, Secret Manager payload, Vertex/Gemini endpoint, or remediation endpoint was modified.

### Decisions made

1. Deployment preflight must treat CLI process reliability as part of the fail-closed security boundary, not as an unhandled operational exception.
2. Synthetic runner failures use stable generic messages. Raw exception text is intentionally discarded because it can contain command arguments, local paths, or other operator context that should not be copied into machine-readable deployment reports.
3. Existing gcloud stderr remains consumed by individual check logic; the new exception path does not introduce a second reporting channel or leak subprocess diagnostics to stdout/stderr.
4. Exit codes 124/126 are internal sentinel values only; deploy readiness still derives from required check status, not from trusting these codes as success/failure policy by themselves.
5. No CI was enabled for the new tests to avoid unnecessary Actions usage.

### Current blockers / unknowns

- The exact committed `runtime.tests.test_gcp_deploy_doctor_process_failures`, fake-gcloud suite, and broader doctor suite still need execution from a runnable repository checkout.
- The historical full suite still needs systematic triage after repository execution is available.
- The exact Cloud Storage object Policy Troubleshooter tuple still needs one authorized disposable-project acceptance run.
- `ENABLE_GEMINI=true python scripts/gcp_deploy_doctor.py --json` still needs a live authorized disposable GCP project.
- `python scripts/gemini_acceptance_smoke.py --execute --json` still needs one real Vertex AI acceptance run after the doctor passes.
- Process failures are now safe, but the first auth-stage runner timeout/executable race is still summarized as the generic `gcloud_auth` failure text. This is fail-closed but operationally imprecise.

## Single best next step

**Make gcloud process-failure classification explicit in the deployment report: distinguish timeout/execution failure from genuine authentication denial without exposing raw subprocess context, and add regression coverage proving later command failures (region/API/secret/storage/IAM/image probes) retain their specific check names while reporting a sanitized process-failure reason.**

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
- Deployment-doctor gcloud timeouts, OS invocation failures, and decode failures now fail closed through sanitized nonzero results instead of escaping as exceptions.
- Gemini acceptance smoke defaults to zero model calls and requires explicit `--execute`.
- Standard Cloud Run deployment keeps production remediation disabled.

## Validation baseline retained

- Local onboarding doctor: 8 tests passed, 1 expected platform-specific permission test skipped on Windows.
- Focused core/API/UI suite from the last executable run: 81/81 passed.
- Historical full suite baseline: 352 tests, 9 failures, 15 errors, 19 skipped; no full-suite green claim.
- Live Docker rehearsal: PASS twice consecutively.
- Official Grafana MCP read-only smoke path: PASS using `grafana/mcp-grafana:1.3.0`.
- Incident flow: investigate -> diagnose `uplink-b packet loss` -> exact revision approval -> bounded remediation -> telemetry-verified recovered.

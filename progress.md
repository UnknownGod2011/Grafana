# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the indispensable runtime evidence plane. The working vertical slice remains: deterministic telemetry, Prometheus/Loki/Grafana, official read-only Grafana MCP access, bounded diagnosis, optional revision-bound Gemini briefing, exact human approval, safe remediation, Grafana-based recovery verification, authenticated lifecycle state, restart reconciliation, and a same-origin operator cockpit.

Core invariants:
- Grafana is the evidence plane; infrastructure write credentials stay isolated from Grafana/MCP access.
- Gemini is optional/advisory and cannot mutate diagnosis, approval, remediation, or recovery state.
- Human approval is single-use and bound to the exact evidence revision.
- Remediation success is never inferred from an action response; fresh Grafana telemetry must prove recovery.
- Authenticated checkpoints and audit integrity fail closed.

## Run log — 2026-09-10 — probe-specific gcloud process failure diagnostics

### Inspected at start

Read `progress.md` completely before choosing work. Inspected the current repository state and the deployment-preflight surface, especially:
- `scripts/gcp_deploy_doctor.py`
- `runtime/tests/test_gcp_deploy_doctor_process_failures.py`
- the retained deployment-doctor fake-gcloud and identifier-parity work recorded in the previous handoff.

The previous handoff identified a concrete operational gap: `_run_gcloud()` already converted subprocess timeout/OS/decode failures into safe internal sentinel return codes, but individual preflight probes still collapsed those failures into ordinary domain messages such as “no active gcloud account,” “could not list enabled APIs,” or “secret not found.” That behavior was fail-closed but could send an operator toward the wrong remediation path.

### Exact changes made

1. Hardened `scripts/gcp_deploy_doctor.py` with explicit process-failure classification.
   - Added `_process_failure_detail(code, operation)`.
   - Only StageGuard’s internal process sentinel codes are classified:
     - `124` -> `gcloud process timed out while <safe operation>`
     - `126` -> `gcloud process could not be executed while <safe operation>`
   - All normal/non-sentinel gcloud exit codes retain the existing authentication/access/not-found semantics. This prevents genuine permission denial or provider CLI errors from being mislabeled as process failures.
   - Operation labels are static strings controlled by StageGuard; raw command arguments, secret IDs, bucket names, image references, exception text, and subprocess stderr are not interpolated into process-failure diagnostics.

2. Preserved probe identity while improving diagnostics for every current live preflight stage.
   - `gcloud_auth`: process failure while checking active authentication.
   - `project_access`: process failure while checking target project access.
   - `cloud_run_region_available`: process failure while checking live Cloud Run region availability.
   - `apis`: process failure while checking enabled APIs.
   - `secret:<ENV>`: process failure while checking Secret Manager resource existence.
   - `checkpoint_bucket_exists`: process failure while checking checkpoint bucket existence.
   - `secret_access:*`, `logging_access:*`, `checkpoint_storage_access:*`, and `vertex_access:predict`: process failure while checking effective IAM access through Policy Troubleshooter.
   - `image_exists`: process failure while checking Artifact Registry image existence.

3. Expanded `runtime/tests/test_gcp_deploy_doctor_process_failures.py`.
   - Verifies only sentinel codes 124/126 receive process classification; ordinary nonzero codes remain unclassified so existing domain semantics are preserved.
   - Verifies auth timeout now reports a precise sanitized process reason.
   - Verifies Cloud Run region timeout retains the `cloud_run_region_available` semantic check name.
   - Verifies IAM process failure retains the requested IAM check name.
   - Adds a late-stage dispatcher test in which region, API, Secret Manager, checkpoint bucket, IAM, and Artifact Registry probes fail through mixed timeout/execution sentinels. Each resulting check must keep its own semantic name and sanitized operation-specific reason.
   - Verifies synthetic subprocess diagnostics and configured secret/bucket identifiers are not copied into the emitted check details.
   - Retains the subprocess-level nonzero fake-gcloud case and explicitly verifies an ordinary exit 125 is still reported as an authentication failure rather than an internal process failure.

Commits:
- `c7a8ff391636ea1142eb39ad8d8e06ee67619254` — classify gcloud process failures per preflight probe
- `c1210498b05bb698f1aa4fadba51b7d5faad49ad` — cover probe-specific gcloud process failure diagnostics

### Tests / checks / results

Execution evidence available in this run:
- Re-fetched and reviewed the committed `_run_gcloud()` / `_process_failure_detail()` implementation after the write.
- Reviewed the committed regression logic for probe-specific classification.
- Attempted a fresh repository clone for direct unittest execution, but the execution container again failed DNS resolution for `github.com` before checkout. Therefore the exact committed unittest modules were not executed and no new full-suite green claim is made.

No GitHub Actions workflow was created, triggered, or rerun. No Grafana instance, MCP server, Google Cloud project, Cloud Run service, bucket/object, IAM policy, Secret Manager payload, Vertex/Gemini endpoint, or remediation endpoint was modified.

### Decisions made

1. Process-failure classification is keyed only from StageGuard-owned sentinel codes, not from arbitrary gcloud exit codes or stderr text.
2. Check names remain the stable machine-readable semantic identity. Process classification improves `detail` only; it does not create a parallel error taxonomy that downstream tooling must reconcile.
3. Static operation labels are intentionally generic enough to avoid leaking configured resource identifiers while still telling an operator whether the failing layer is authentication, project access, region discovery, API discovery, Secret Manager, storage, IAM, or image resolution.
4. Ordinary gcloud command failures continue to use existing access/not-found/authentication wording because those may represent permissions, configuration, provider/API, or account state rather than a broken local subprocess.
5. No CI was enabled for these tests to avoid noisy GitHub Actions usage.

### Current blockers / unknowns

- The exact committed `runtime.tests.test_gcp_deploy_doctor_process_failures`, fake-gcloud suite, and broader doctor suite still need execution from a runnable repository checkout.
- The historical full suite still needs systematic triage after repository execution is available.
- The exact Cloud Storage object Policy Troubleshooter tuple still needs one authorized disposable-project acceptance run.
- `ENABLE_GEMINI=true python scripts/gcp_deploy_doctor.py --json` still needs a live authorized disposable GCP project.
- `python scripts/gemini_acceptance_smoke.py --execute --json` still needs one real Vertex AI acceptance run after the doctor passes.
- The doctor currently preserves failure semantics in `detail`, but its JSON contract does not expose a compact machine-readable failure category (`timeout`, `execution`, `auth`, `access`, `provider`, etc.). Adding one directly to `Check` would be a schema change and should be evaluated carefully against existing tests/consumers before doing so.

## Single best next step

**Execute the focused deployment-doctor suites from a runnable checkout and, once green, audit downstream consumers of the doctor JSON before deciding whether a backward-compatible machine-readable failure category is justified. If execution remains unavailable, shift to an unblocked production area rather than repeatedly hardening the same preflight surface.**

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
- Deployment-doctor gcloud timeouts, OS invocation failures, and decode failures fail closed through sanitized nonzero results and now retain probe-specific operational diagnostics.
- Gemini acceptance smoke defaults to zero model calls and requires explicit `--execute`.
- Standard Cloud Run deployment keeps production remediation disabled.

## Validation baseline retained

- Local onboarding doctor: 8 tests passed, 1 expected platform-specific permission test skipped on Windows.
- Focused core/API/UI suite from the last executable run: 81/81 passed.
- Historical full suite baseline: 352 tests, 9 failures, 15 errors, 19 skipped; no full-suite green claim.
- Live Docker rehearsal: PASS twice consecutively.
- Official Grafana MCP read-only smoke path: PASS using `grafana/mcp-grafana:1.3.0`.
- Incident flow: investigate -> diagnose `uplink-b packet loss` -> exact revision approval -> bounded remediation -> telemetry-verified recovered.

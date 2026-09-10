# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the indispensable runtime evidence plane. The working vertical slice remains: deterministic telemetry, Prometheus/Loki/Grafana, official read-only Grafana MCP access, bounded diagnosis, optional revision-bound Gemini briefing, exact human approval, safe remediation, Grafana-based recovery verification, authenticated lifecycle state, restart reconciliation, and a same-origin operator cockpit.

Core invariants:
- Grafana is the evidence plane; infrastructure write credentials stay isolated from Grafana/MCP access.
- Gemini is optional/advisory and cannot mutate diagnosis, approval, remediation, or recovery state.
- Human approval is single-use and bound to the exact evidence revision.
- Remediation success is never inferred from an action response; fresh Grafana telemetry must prove recovery.
- Authenticated checkpoints and audit integrity fail closed.

## Run log — 2026-09-10 — Cloud Run serialization/injection hardening

### Inspected at start

Read `progress.md` completely before choosing work. Then inspected:
- `scripts/deploy_cloud_run.sh`
- `runtime/tests/test_cloud_run_deploy_shell.py`
- `runtime/tests/test_cloud_run_deploy_contract.py`
- `scripts/gcp_deploy_doctor.py`
- `runtime/tests/test_gcp_deploy_doctor.py`
- recent `main` commits to verify no newer work superseded the handoff

The previous handoff requested behavioral proof that secret payloads cannot leak into deployment arguments and that malformed Gemini settings fail before `gcloud`. Inspection also exposed a broader production boundary: multiple operator-controlled values are interpolated into comma-delimited `gcloud --set-env-vars` / `--set-secrets` mappings, so comma/control injection must fail even if the deployment doctor is skipped.

### Exact changes made

1. Hardened `scripts/deploy_cloud_run.sh` before any `gcloud` invocation:
   - `PROJECT_NUMBER` must be numeric.
   - `RUNTIME_SERVICE_ACCOUNT` must be a service-account email without commas/whitespace.
   - `GRAFANA_URL` must be an absolute HTTP(S) URL without commas/whitespace.
   - `IAP_AUDIENCE` and `IMAGE_URL` reject commas, whitespace, and control characters at the command serialization boundary.
   - all five Secret Manager identifiers are restricted to bounded `[A-Za-z0-9_-]{1,255}` IDs.
   - existing strict `ENABLE_GEMINI`, Gemini location/model, checkpoint bucket, and UTF-8 checkpoint-object validation remains in place.
   - HMAC material remains Secret Manager resolved; no payload variable is serialized into `ENV_VARS`.

   Commit:
   - `1b6805e5f99cb93530489a34f58f2628e2306c64` — harden Cloud Run deploy argument boundaries

2. Expanded `runtime/tests/test_cloud_run_deploy_shell.py`:
   - generalized the fake-`gcloud` harness to support environment overrides;
   - verifies a synthetic `STAGEGUARD_CHECKPOINT_HMAC_KEY` payload sentinel never reaches captured deployment arguments;
   - verifies the checkpoint HMAC *secret identifier* is present only through the `--set-secrets` mapping;
   - verifies Grafana URL, IAP audience, Secret Manager mapping, runtime-service-account, and project-number injection attempts fail before `gcloud`;
   - verifies invalid `ENABLE_GEMINI`, Gemini location, and Gemini model values fail before `gcloud`;
   - retains the 512-byte/513-byte/multibyte/whitespace checkpoint-object execution checks.

   Commit:
   - `ecf856bb2cb8a2aa679193469f60b7f39c3fb6e9` — exercise Cloud Run config injection guards

3. Aligned `scripts/gcp_deploy_doctor.py` with the deployment helper so offline preflight no longer reports a value acceptable when the shell will later reject it:
   - added bounded Secret Manager ID validation for every runtime secret reference;
   - added IAP audience command-serialization safety validation;
   - added required image-reference command-serialization safety validation while retaining the Artifact Registry shape check as advisory;
   - tightened Grafana URL and runtime service-account comma handling;
   - added actionable next-step guidance for serialization/secret-ID failures.

   Commit:
   - `f0b4b1588375fa4382f664e0b03e551b3f5ca3c6` — align deploy doctor with shell serialization guards

4. Added `runtime/tests/test_gcp_deploy_doctor_serialization.py`:
   - proves a valid offline configuration passes the new serialization checks;
   - rejects IAP audience comma injection;
   - rejects image-reference comma injection;
   - rejects Secret Manager mapping injection;
   - enforces the 255-character secret-ID bound.

   Commit:
   - `1e035f3e74b4acdc7f0e65054bd80819c9bf99a8` — test deploy doctor serialization parity

### Tests / checks / results

A local, credential-free fake-`gcloud` reproduction of the new shell guards was executed and all 6 focused behavioral checks passed:

```text
test_gemini ... ok
test_grafana ... ok
test_iap ... ok
test_secret ... ok
test_secret_inject ... ok
test_valid ... ok
Ran 6 tests ... OK
```

This reproduction exercised the same committed guard logic with synthetic values and no network/cloud access. It is useful behavioral evidence, but it is not represented as the complete committed unittest file.

A fresh clean-checkout execution of the actual committed suites was then attempted:

```text
git clone --depth 1 https://github.com/UnknownGod2011/Grafana.git /tmp/stageguard-run
python -m unittest runtime.tests.test_cloud_run_deploy_shell runtime.tests.test_gcp_deploy_doctor_serialization runtime.tests.test_cloud_run_deploy_contract runtime.tests.test_gcp_deploy_doctor -v
```

The container again failed at clone time because DNS could not resolve `github.com`. Therefore the exact committed combined suite was not executed here and no full green claim is made.

No GitHub Actions workflow was created, triggered, or rerun. No Grafana instance, MCP server, Google Cloud project, bucket, object, IAM policy, Secret Manager payload, Gemini endpoint, or remediation endpoint was modified.

### Decisions made

1. `deploy_cloud_run.sh` must independently fail closed at every comma-delimited `gcloud` serialization boundary; the deployment doctor is defense-in-depth, not a prerequisite for safe parsing.
2. Secret-name variables accept Secret Manager IDs only. They must never be usable as arbitrary `--set-secrets` fragments.
3. Secret payload environment variables supplied accidentally by an operator are ignored by the deploy helper and must never be forwarded.
4. The deployment doctor and deployment shell should share acceptance boundaries wherever practical so `offline_checks_passed=true` predicts shell acceptance.
5. Artifact Registry shape remains advisory in the doctor, while command-line serialization safety is required.

### Current blockers / unknowns

- The exact committed shell + doctor serialization suites still need execution from a runnable checkout.
- The broader focused deployment/entrypoint/doctor suites still need empirical execution from a runnable checkout.
- The exact Cloud Storage object Policy Troubleshooter tuple still needs one authorized disposable-project acceptance run.
- `ENABLE_GEMINI=true python scripts/gcp_deploy_doctor.py --json` still needs a live authorized disposable GCP project.
- `python scripts/gemini_acceptance_smoke.py --execute --json` still needs one real Vertex AI acceptance run after the doctor passes.
- Historical full-suite failures/errors still need systematic triage after the repository can be executed locally.

## Single best next step

**Execute the exact committed Cloud Run shell/doctor suites from a runnable checkout. If green, audit `PROJECT_ID`, `REGION`, `SERVICE_NAME`, and `IMAGE_URL` against Google Cloud's current documented identifier/reference grammar and centralize those deployment validators so `deploy_cloud_run.sh` and `gcp_deploy_doctor.py` cannot drift. Then add parity tests for those identifiers before expanding deployment behavior.**

## Previous run — executable fake-gcloud deployment boundary harness

The previous run added `runtime/tests/test_cloud_run_deploy_shell.py`, executing the real production deployment helper against an isolated fake `gcloud` and covering checkpoint object UTF-8 boundaries plus fail-before-external-call behavior.

Previous commits:
- `60538f0820dcf575886b76c36a951be06db9059c` — test Cloud Run deploy helper with fake gcloud
- `a525c4a4f21e132f78c1d46ef087477830266e6c` — record fake gcloud deployment harness progress

## Retained production hardening

- Cloud Run production deployment uses authenticated GCS checkpoints rather than silent ephemeral/no-checkpoint state.
- Runtime checkpoint HMAC keys are Secret Manager supplied and at least 32 UTF-8 bytes.
- Checkpoint object validation is byte-accurate and aligned across deploy helper, deployment doctor, and runtime.
- Cloud Run deployment now rejects malformed/injected comma-delimited environment and secret mapping inputs before `gcloud`.
- Runtime MCP launcher parsing is centralized and cross-platform.
- Readiness validates local activation/pin trust before spawning/querying Grafana MCP.
- Deployment doctor validates required APIs, secrets/access, Cloud Logging permissions, checkpoint storage permissions, conditional Vertex prediction permission, image availability, and deployment serialization boundaries; offline validation can never report deploy-ready.
- Gemini acceptance smoke defaults to zero model calls and requires explicit `--execute`.
- Standard Cloud Run deployment keeps production remediation disabled.

## Validation baseline retained

- Local onboarding doctor: 8 tests passed, 1 expected platform-specific permission test skipped on Windows.
- Focused core/API/UI suite from the last executable run: 81/81 passed.
- Historical full suite baseline: 352 tests, 9 failures, 15 errors, 19 skipped; no full-suite green claim.
- Live Docker rehearsal: PASS twice consecutively.
- Official Grafana MCP read-only smoke path: PASS using `grafana/mcp-grafana:1.3.0`.
- Incident flow: investigate -> diagnose `uplink-b packet loss` -> exact revision approval -> bounded remediation -> telemetry-verified recovered.

# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the indispensable runtime evidence plane. The working vertical slice remains: deterministic telemetry, Prometheus/Loki/Grafana, official read-only Grafana MCP access, bounded diagnosis, optional revision-bound Gemini briefing, exact human approval, safe remediation, Grafana-based recovery verification, authenticated lifecycle state, restart reconciliation, and a same-origin operator cockpit.

Core invariants remain unchanged:
- Grafana is the evidence plane; infrastructure write credentials stay isolated from Grafana/MCP access.
- Gemini is optional/advisory and cannot mutate diagnosis, approval, remediation, or recovery state.
- Human approval is single-use and bound to the exact evidence revision.
- Remediation success is never inferred from an action response; fresh Grafana telemetry must prove recovery.
- Authenticated checkpoints and audit integrity fail closed.

## Run log — 2026-09-10 — checkpoint deploy/runtime validation parity

### Inspected at start

Read `progress.md` completely before choosing work. Then inspected:
- `scripts/deploy_cloud_run.sh`
- `scripts/gcp_deploy_doctor.py`
- `runtime/cloudrun_entrypoint.py`
- `runtime/bootstrap.py`
- `runtime/incident_checkpoint.py`
- `runtime/tests/test_cloud_run_deploy_contract.py`

Also reviewed current Google Cloud IAM / Policy Troubleshooter / Cloud Storage permission documentation while checking whether the previous GCS preflight work required another permission change. No additional runtime storage permission was justified; `storage.objects.get/create/delete` remains the bounded checkpoint contract.

### Concrete defect found

The standard Cloud Run deploy helper and the runtime disagreed on `CHECKPOINT_OBJECT` validation:
- `runtime/cloudrun_entrypoint.py` rejects object paths longer than 512 **UTF-8 bytes** and rejects leading/trailing whitespace because it requires `raw == raw.strip()`.
- `scripts/gcp_deploy_doctor.py` already uses the same UTF-8 byte bound.
- `scripts/deploy_cloud_run.sh` used Bash `${#CHECKPOINT_OBJECT}`, which is a character count under normal UTF-8 locales, and did not reject leading/trailing whitespace.

That meant an operator could pass the deployment helper with a multibyte object name that was <=512 characters but >512 bytes, or with leading/trailing whitespace, only for the Cloud Run container to fail closed during startup. This was a real deployment/runtime contract bug, not a documentation-only issue.

### Exact changes made

Updated `scripts/deploy_cloud_run.sh`:
- added fail-closed leading/trailing whitespace guards for `CHECKPOINT_OBJECT`;
- replaced the character-count limit with a byte-count check using `LC_ALL=C`, `printf`, and `wc -c`;
- rejects unreadable/non-numeric byte-count output defensively;
- updated the error contract to state the 512 UTF-8 byte limit explicitly;
- preserved all existing protections against empty paths, leading/trailing `/`, empty segments, `.`/`..`, commas, backslashes, and control characters;
- preserved remediation-disabled production deployment and Secret Manager handling.

Updated `runtime/tests/test_cloud_run_deploy_contract.py`:
- added runtime entrypoint and deploy-doctor sources to the deployment contract fixture;
- added a regression assertion that deploy helper, doctor, and runtime all use the 512 UTF-8-byte boundary;
- explicitly prevents regression to `${#CHECKPOINT_OBJECT}` character-count validation;
- added leading/trailing whitespace parity assertions and verifies those guards execute before `gcloud run deploy`.

Commits created this run:
- `49b379f6875b103c2ac9b6ff913ee21ad6fe05ae` — align checkpoint object validation with runtime
- `f3330555ae4a7bf724c95b0ccf92ac4eee9a7a1a` — cover checkpoint object deploy parity

### Tests / checks / results

Attempted the focused suite from a fresh checkout before making speculative changes:

```text
git clone --depth 1 https://github.com/UnknownGod2011/Grafana.git /tmp/stageguard
python -m unittest runtime.tests.test_gcp_deploy_doctor runtime.tests.test_cloud_run_deploy_contract runtime.tests.test_cloudrun_entrypoint
```

The execution container still failed at clone time because DNS could not resolve `github.com`. Therefore the focused suite was not empirically executed in this runtime and no green-suite claim is made.

Source-level verification through the GitHub connector confirmed the committed deploy helper now contains the byte-bound and whitespace guards and the regression contract references the exact runtime/doctor behavior.

No GitHub Actions workflow was created, triggered, or rerun. No Grafana instance, MCP server, Google Cloud project, bucket, object, IAM policy, Secret Manager payload, Gemini endpoint, or remediation endpoint was modified.

### Decisions made

1. Deployment validation must be at least as strict as container-start validation; production should fail before `gcloud run deploy` when possible.
2. Checkpoint object limits are measured in UTF-8 bytes consistently across doctor, deploy helper, and runtime.
3. No extra Cloud Storage runtime permissions were added; current Google Cloud documentation still supports the existing `get/create/delete` object permission model for StageGuard's generation-controlled single-object checkpoint store.
4. Missing cloud credentials remain a reason to avoid destructive/live acceptance, not a reason to stop credential-free hardening.

### Current blockers / unknowns

- The focused deployment/entrypoint tests still need empirical execution from a runnable checkout.
- The exact Cloud Storage object Policy Troubleshooter tuple still needs one authorized disposable-project acceptance run.
- `ENABLE_GEMINI=true python scripts/gcp_deploy_doctor.py --json` still needs a live authorized disposable GCP project.
- `python scripts/gemini_acceptance_smoke.py --execute --json` still needs one real Vertex AI acceptance run after the doctor passes.
- Historical full-suite failures/errors still need systematic triage after the repository can be executed locally.

## Single best next step

**As soon as a runnable checkout is available, run `runtime.tests.test_cloud_run_deploy_contract`, `runtime.tests.test_cloudrun_entrypoint`, and `runtime.tests.test_gcp_deploy_doctor`, then execute the deploy helper against a fake `gcloud` shim with boundary inputs (ASCII 512/513 bytes, multibyte <=512 characters but >512 bytes, and leading/trailing whitespace) so the shell behavior itself—not only source assertions—is regression-tested without touching Google Cloud.**

## Previous run — durable checkpoint deployment preflight parity

The previous run aligned `scripts/gcp_deploy_doctor.py` with mandatory authenticated GCS checkpoints. It added required checkpoint inputs, `storage.googleapis.com`, checkpoint-HMAC Secret Manager checks, bucket metadata checks, and fail-closed Policy Troubleshooter evaluation for `storage.objects.get`, `storage.objects.create`, and `storage.objects.delete` on the configured checkpoint object. It also expanded deployment documentation and credential-free regression coverage.

Previous commits:
- `aebbab227f2b6b7743b71a6840fd6c2403d60c8b` — harden deploy doctor for durable GCS checkpoints
- `df64438c9bb5844c41e2382e35f91e85549a5396` — cover durable checkpoint deployment preflight
- `e2c426d46d260b5a9b0b4afe84027d17b81b011a` — document durable checkpoint IAM contract

## Retained production hardening

- Cloud Run production deployment uses authenticated GCS checkpoints rather than silent ephemeral/no-checkpoint state.
- Runtime checkpoint HMAC keys are Secret Manager supplied and at least 32 UTF-8 bytes.
- Checkpoint object validation is now byte-accurate and aligned across deploy helper, doctor, and runtime.
- Runtime MCP launcher parsing is centralized and cross-platform.
- Readiness validates local activation/pin trust before spawning/querying Grafana MCP.
- Deployment doctor validates required APIs, secrets/access, Cloud Logging permissions, checkpoint storage permissions, conditional Vertex prediction permission, and image availability; offline validation can never report deploy-ready.
- Gemini acceptance smoke defaults to zero model calls and requires explicit `--execute`.
- Standard Cloud Run deployment keeps production remediation disabled.

## Validation baseline retained

- Local onboarding doctor: 8 tests passed, 1 expected platform-specific permission test skipped on Windows.
- Focused core/API/UI suite from the last executable run: 81/81 passed.
- Historical full suite baseline: 352 tests, 9 failures, 15 errors, 19 skipped; no full-suite green claim.
- Live Docker rehearsal: PASS twice consecutively.
- Official Grafana MCP read-only smoke path: PASS using `grafana/mcp-grafana:1.3.0`.
- Incident flow: investigate -> diagnose `uplink-b packet loss` -> exact revision approval -> bounded remediation -> telemetry-verified recovered.

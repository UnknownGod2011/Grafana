# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the indispensable runtime evidence plane. The working vertical slice remains: deterministic telemetry, Prometheus/Loki/Grafana, official read-only Grafana MCP access, bounded diagnosis, optional revision-bound Gemini briefing, exact human approval, safe remediation, Grafana-based recovery verification, authenticated lifecycle state, restart reconciliation, and a same-origin operator cockpit.

Core invariants:
- Grafana is the evidence plane; infrastructure write credentials stay isolated from Grafana/MCP access.
- Gemini is optional/advisory and cannot mutate diagnosis, approval, remediation, or recovery state.
- Human approval is single-use and bound to the exact evidence revision.
- Remediation success is never inferred from an action response; fresh Grafana telemetry must prove recovery.
- Authenticated checkpoints and audit integrity fail closed.

## Run log — 2026-09-10 — deploy doctor identifier parity

### Inspected at start

Read `progress.md` completely before choosing work, then inspected the repository root and the deployment boundary files most relevant to the previous handoff:
- `scripts/gcp_deploy_doctor.py`
- `scripts/gcp_identifiers.py`
- `runtime/tests/test_gcp_deploy_doctor_serialization.py`
- current root repository structure on `main`

The previous handoff correctly identified a contract drift: `scripts/deploy_cloud_run.sh` already used the centralized `gcp_identifiers.py`, but the doctor still carried independent project/service/region/image logic and treated some invalid image forms as only warnings.

### Exact changes made

1. Refactored `scripts/gcp_deploy_doctor.py` to import and use the shared pure validators for:
   - `PROJECT_ID`;
   - `REGION`;
   - `SERVICE_NAME`;
   - `IMAGE_URL`.

   Identifier failures are now required/fail-closed doctor checks rather than warnings. In particular, unversioned Artifact Registry images and non-Artifact-Registry images can no longer pass offline doctor validation when the production deploy helper would reject them.

   Commit:
   - `e1324166a3034331a05287b3abe4a212ae65e1cc` — align deploy doctor with shared Google Cloud identifier validation

2. Corrected one overly restrictive intermediate policy discovered during the refactor. Cross-project Artifact Registry images are legitimate deployment inputs, so the doctor does not require the image's project component to equal `PROJECT_ID`; it now matches the deploy helper's actual shared-validator contract instead of inventing an extra policy restriction.

   Commit:
   - `26163bd9e7b38e2aa0ae1652b2d97e21c82ca831` — preserve cross-project Artifact Registry deployment parity

3. Expanded `runtime/tests/test_gcp_deploy_doctor_serialization.py` so offline doctor behavior now explicitly covers:
   - valid project/region/service/image checks;
   - malformed uppercase project IDs;
   - malformed region identifiers;
   - malformed Cloud Run service names;
   - unversioned Artifact Registry images as required failures;
   - non-Artifact-Registry images as required failures;
   - cross-project tagged Artifact Registry images as valid;
   - all previously retained injection/secret-name serialization checks.

   Commit:
   - `9e8947f06a6a6d6e7d8add7b604f2b819cfdc912` — cover deploy doctor identifier parity

### Tests / checks / results

Attempted a clean checkout followed by:

`python3 -m unittest runtime.tests.test_gcp_identifiers runtime.tests.test_gcp_deploy_doctor_serialization runtime.tests.test_cloud_run_deploy_shell`

The execution container still cannot resolve `github.com`; `git clone` failed before checkout with `Could not resolve host: github.com`. Therefore the exact committed focused suite was not executed and no green-suite claim is made.

The GitHub connector itself remained usable for repository inspection and commits. No GitHub Actions workflow was created, triggered, or rerun. No Grafana instance, MCP server, Google Cloud project, Cloud Run service, bucket/object, IAM policy, Secret Manager payload, Gemini endpoint, or remediation endpoint was modified.

### Decisions made

1. Deployment identifier grammar now has one source of truth: `scripts/gcp_identifiers.py`.
2. The deployment doctor treats production deploy-helper identifier rejection as a required preflight failure, not a warning.
3. StageGuard intentionally allows cross-project Artifact Registry images; registry authorization/existence is a live cloud concern, not a local grammar restriction.
4. No hard-coded Cloud Run region allowlist is introduced. Provider availability should be checked read-only at runtime because supported regions can change.

### Current blockers / unknowns

- The exact identifier + deploy-doctor + fake-`gcloud` focused suites still need execution from a runnable checkout.
- A read-only live Cloud Run region availability check has not yet been added to `gcp_deploy_doctor.py`.
- The exact Cloud Storage object Policy Troubleshooter tuple still needs one authorized disposable-project acceptance run.
- `ENABLE_GEMINI=true python scripts/gcp_deploy_doctor.py --json` still needs a live authorized disposable GCP project.
- `python scripts/gemini_acceptance_smoke.py --execute --json` still needs one real Vertex AI acceptance run after the doctor passes.
- Historical full-suite failures/errors still need systematic triage after the repository can be executed locally.

## Single best next step

**Add a read-only Cloud Run region availability preflight to `gcp_deploy_doctor.py` using the active gcloud environment, fail closed if the configured `REGION` is not currently supported/visible for Cloud Run, and cover the command/result parsing with a fake-gcloud test so no static region allowlist is required.**

## Retained production hardening

- Cloud Run production deployment uses authenticated GCS checkpoints rather than silent ephemeral/no-checkpoint state.
- Runtime checkpoint HMAC keys are Secret Manager supplied and at least 32 UTF-8 bytes.
- Checkpoint object validation is byte-accurate and aligned across deploy helper, deployment doctor, and runtime.
- Cloud Run deployment rejects malformed/injected comma-delimited environment and secret mapping inputs before `gcloud`.
- Google Cloud project/region/service/image identifier grammar is centralized and shared by the deploy helper and deployment doctor.
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

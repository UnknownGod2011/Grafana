# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the indispensable runtime evidence plane. The working vertical slice remains: deterministic telemetry, Prometheus/Loki/Grafana, official read-only Grafana MCP access, bounded diagnosis, optional revision-bound Gemini briefing, exact human approval, safe remediation, Grafana-based recovery verification, authenticated lifecycle state, restart reconciliation, and a same-origin operator cockpit.

Core invariants:
- Grafana is the evidence plane; infrastructure write credentials stay isolated from Grafana/MCP access.
- Gemini is optional/advisory and cannot mutate diagnosis, approval, remediation, or recovery state.
- Human approval is single-use and bound to the exact evidence revision.
- Remediation success is never inferred from an action response; fresh Grafana telemetry must prove recovery.
- Authenticated checkpoints and audit integrity fail closed.

## Run log — 2026-09-10 — live Cloud Run region availability

### Inspected at start

Read `progress.md` completely before choosing work, then inspected the current repository root and the deployment boundary most relevant to the previous handoff:
- `scripts/gcp_deploy_doctor.py`
- `scripts/gcp_identifiers.py`
- `runtime/tests/test_gcp_deploy_doctor.py`
- recent deployment-doctor commits on `main`

The previous handoff identified the highest-value next gap correctly: `REGION` had local grammar validation but no live provider availability check, so a syntactically valid but unsupported/stale Cloud Run region could still survive preflight until deployment.

### Research / attribution

Verified against current official Google Cloud CLI documentation that `gcloud run regions list` is the supported read-only command for listing available Cloud Run fully managed regions. The doctor now uses that provider result rather than a repository-maintained allowlist.

Official references consulted:
- https://docs.cloud.google.com/sdk/gcloud/reference/run/regions/list
- https://docs.cloud.google.com/sdk/gcloud/reference/run/regions

### Exact changes made

1. Added a live Cloud Run region availability check to `scripts/gcp_deploy_doctor.py`.
   - Executes `gcloud run regions list --project=<PROJECT_ID> --format=value(locationId)` only in the live/non-offline preflight path.
   - Parses the provider-reported region catalog without a static allowlist.
   - Reports `cloud_run_region_available=ok` only when the configured `REGION` is present.
   - Fails closed when the command fails, returns an empty/unusable catalog, or omits the configured region.
   - Adds an actionable next step directing the operator to the live `gcloud run regions list` output.

   Commit:
   - `b4171deef7820795f8369457fa5e88f4caa3711b` — verify live Cloud Run region availability in deploy doctor

2. Expanded `runtime/tests/test_gcp_deploy_doctor.py`.
   - Added coverage for the exact read-only command shape.
   - Added supported-region success coverage.
   - Added fail-closed cases for unsupported region, empty provider output, and command failure.
   - Added next-step coverage for live region selection.
   - Fixed the test module loader so `scripts/gcp_identifiers.py` is importable when the doctor is loaded directly with `importlib`.

3. Removed a stale regression expectation in `runtime/tests/test_gcp_deploy_doctor.py` that still treated non-Artifact-Registry images as optional warnings. The production doctor now intentionally rejects those images, so the test now expects a required failure and exit code 2. This aligns the older test file with the centralized identifier contract already implemented in previous runs.

   Commit:
   - `3852c551c69ec6d4c71cd159e2e74079b76c23eb` — cover live Cloud Run region preflight

### Tests / checks / results

Attempted a clean repository checkout first so the exact committed tests could run. The execution container still cannot resolve `github.com`; `git clone` failed with `Could not resolve host: github.com`. Therefore the exact committed unittest suite was not executed and no green-suite claim is made.

Performed additional validation despite that transient environment limitation:
- inspected both committed diffs through the GitHub API after each write;
- re-fetched the updated region-check section from `main` and verified the live check is wired into `_gcloud_checks()` and `_next_steps()`;
- ran a credential-free local parser micro-harness covering supported, unsupported, empty-output, and command-failure cases: **4/4 passed**.

No GitHub Actions workflow was created, triggered, or rerun. No Grafana instance, MCP server, Google Cloud project, Cloud Run service, bucket/object, IAM policy, Secret Manager payload, Gemini endpoint, or remediation endpoint was modified.

### Decisions made

1. Cloud Run region availability is a live provider fact, not a static repository constant.
2. Region-catalog lookup is read-only and belongs only to live preflight; `--offline` remains fully credential/network independent.
3. A failure to obtain a usable provider region catalog is a required failure. The doctor must not guess deployability from local region syntax alone.
4. Existing deployment image policy remains fail-closed: production `IMAGE_URL` must be an explicitly tagged or sha256-pinned Artifact Registry image.
5. Direct test-module loading now explicitly exposes the `scripts/` directory to Python imports, avoiding a test-loader-only failure unrelated to product behavior.

### Current blockers / unknowns

- The exact deployment-doctor test suite still needs execution from a runnable checkout.
- The full historical suite still needs systematic triage after repository execution is available; one stale doctor expectation was corrected in this run.
- The exact Cloud Storage object Policy Troubleshooter tuple still needs one authorized disposable-project acceptance run.
- `ENABLE_GEMINI=true python scripts/gcp_deploy_doctor.py --json` still needs a live authorized disposable GCP project.
- `python scripts/gemini_acceptance_smoke.py --execute --json` still needs one real Vertex AI acceptance run after the doctor passes.
- The live region check currently trusts `gcloud run regions list`'s `locationId` value output; this matches current CLI behavior/documentation conventions but still needs an exact fake-`gcloud` end-to-end doctor test from a runnable checkout.

## Single best next step

**Build an end-to-end fake-`gcloud` harness for live `gcp_deploy_doctor.py --json` that exercises the full read-only command sequence, proves an unsupported/empty Cloud Run region catalog forces `ready_to_deploy=false`, and proves a supported region can progress to the remaining IAM/storage/image checks without any real GCP credentials. Then run that harness plus the focused doctor/identifier/deploy-shell suites when checkout execution is available.**

## Previous run — 2026-09-10 — deploy doctor identifier parity

- Refactored `scripts/gcp_deploy_doctor.py` to share `scripts/gcp_identifiers.py` for `PROJECT_ID`, `REGION`, `SERVICE_NAME`, and `IMAGE_URL`.
- Preserved legitimate cross-project Artifact Registry deployment support.
- Expanded serialization/identifier parity regression coverage.
- Commits: `e1324166a3034331a05287b3abe4a212ae65e1cc`, `26163bd9e7b38e2aa0ae1652b2d97e21c82ca831`, `9e8947f06a6a6d6e7d8add7b604f2b819cfdc912`.
- Exact tests were blocked by the same container DNS failure; no external resources or Actions were touched.

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

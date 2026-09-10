# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the indispensable runtime evidence plane. The working vertical slice remains: deterministic telemetry, Prometheus/Loki/Grafana, official read-only Grafana MCP access, bounded diagnosis, optional revision-bound Gemini briefing, exact human approval, safe remediation, Grafana-based recovery verification, authenticated lifecycle state, restart reconciliation, and a same-origin operator cockpit.

Core invariants:
- Grafana is the evidence plane; infrastructure write credentials stay isolated from Grafana/MCP access.
- Gemini is optional/advisory and cannot mutate diagnosis, approval, remediation, or recovery state.
- Human approval is single-use and bound to the exact evidence revision.
- Remediation success is never inferred from an action response; fresh Grafana telemetry must prove recovery.
- Authenticated checkpoints and audit integrity fail closed.

## Run log — 2026-09-10 — Google Cloud identifier hardening

### Inspected at start

Read `progress.md` completely before choosing work. Then inspected:
- `scripts/deploy_cloud_run.sh`
- `scripts/gcp_deploy_doctor.py`
- `runtime/tests/test_cloud_run_deploy_shell.py`
- `runtime/tests/test_gcp_deploy_doctor_serialization.py`
- recent repository state on `main`

The previous handoff identified `PROJECT_ID`, `REGION`, `SERVICE_NAME`, and `IMAGE_URL` as the next deployment boundary to harden. Current Google Cloud documentation was checked before implementation. The documented project-ID grammar is 6-30 lowercase ASCII letters/digits/hyphens, starting with a letter and not ending with a hyphen. Cloud Run service names are bounded to 1-49 lowercase letters/digits/hyphens. Artifact Registry Docker image references use a `<location>-docker.pkg.dev/<project>/<repository>/<image>:<tag>` or digest form. Cloud Run remains regional, so StageGuard accepts a bounded lowercase region/location identifier shape rather than baking a stale region allowlist into source.

### Exact changes made

1. Added `scripts/gcp_identifiers.py` as a pure, credential-free deployment identifier validator:
   - exact modern Google Cloud project-ID grammar;
   - Cloud Run service-name boundary (1-49 chars, lowercase DNS-like identifier, no trailing hyphen);
   - bounded lowercase region/location shape;
   - tagged or sha256-pinned Artifact Registry Docker image URI parsing;
   - helpers for detecting digest pinning and extracting the image project;
   - CLI exits `2` on invalid deployment identifiers and performs no network calls.

   Commit:
   - `4dee964e7496891731060052eb41280bf6d3fc5b` — centralize Google Cloud deployment identifier validation

2. Updated `scripts/deploy_cloud_run.sh` to invoke the centralized validator before any `gcloud` command:
   - derives the validator path from the deploy script's own location, so invocation does not depend on the current working directory;
   - requires a Python interpreter (`PYTHON_BIN`, default `python3`);
   - validates `PROJECT_ID`, `REGION`, `SERVICE_NAME`, and `IMAGE_URL` before continuing to the existing serialization/secret/checkpoint guards;
   - non-Artifact-Registry and unversioned image references now fail before cloud mutation;
   - all previous fail-closed Secret Manager, checkpoint, Gemini, IAP, Grafana, and remediation-disabled behavior remains intact.

   Commit:
   - `80551796488ef37bcdcd79ec707f9ec661ad25fe` — enforce centralized Google Cloud identifiers in deploy helper

3. Added `runtime/tests/test_gcp_identifiers.py`:
   - project-ID minimum/maximum and invalid capitalization/start/end cases;
   - Cloud Run service-name 1/49-character boundaries and invalid capitalization/start/end cases;
   - representative Cloud Run region shapes;
   - Artifact Registry tagged and sha256 digest references;
   - rejection of unversioned Artifact Registry images, Docker Hub/GCR references, malformed digest values, and uppercase project IDs.

   Commit:
   - `77613b40ea0b2d91bc1a095edabc499c9c99937a` — test centralized Google Cloud deployment identifiers

4. Expanded `runtime/tests/test_cloud_run_deploy_shell.py` so the real deploy helper + fake `gcloud` harness verifies malformed project IDs, regions, Cloud Run service names, non-Artifact-Registry images, and unversioned Artifact Registry images all fail before any external `gcloud` invocation.

   Commit:
   - `9c8810f6d39e90aa7589bd7b5735678b190c1c0d` — cover Cloud Run identifier rejection before gcloud

### Tests / checks / results

The new validator logic was reproduced credential-free in the execution environment and its core boundary assertions passed. The Python process returned `0` and unittest reported `OK`; an unrelated artifact-tool warmup emitted a timeout traceback during Python startup but did not affect the test result.

The repository itself could not be cloned into the execution container because direct container networking/DNS to `github.com` remains unavailable, so the exact committed test files were not executed from a checkout and no full-suite green claim is made.

No GitHub Actions workflow was created, triggered, or rerun. No Grafana instance, MCP server, Google Cloud project, Cloud Run service, bucket, object, IAM policy, Secret Manager payload, Gemini endpoint, or remediation endpoint was modified.

### Decisions made

1. The production deployment helper now requires an Artifact Registry Docker image with an explicit tag or sha256 digest; silently relying on an implicit `latest` is not acceptable for StageGuard deployment reproducibility.
2. StageGuard validates the documented identifier grammar locally before invoking `gcloud`, rather than relying on late provider errors after deployment has begun.
3. Region validation intentionally checks a bounded Google Cloud location-ID shape rather than a hard-coded region allowlist, because supported Cloud Run regions can change; live availability remains a provider-side/read-only preflight concern.
4. The identifier module is pure and credential-free so it can be reused by the deployment doctor and unit tests without importing cloud SDKs or reading secrets.
5. Existing deployment serialization checks remain defense-in-depth even after identifier validation.

### Current blockers / unknowns

- `gcp_deploy_doctor.py` still has its older independent project/service/image checks and has not yet been switched to the new shared `gcp_identifiers.py`; that parity gap is the primary remaining issue from this run.
- The exact committed identifier + fake-gcloud + doctor suites still need execution from a runnable checkout.
- The exact Cloud Storage object Policy Troubleshooter tuple still needs one authorized disposable-project acceptance run.
- `ENABLE_GEMINI=true python scripts/gcp_deploy_doctor.py --json` still needs a live authorized disposable GCP project.
- `python scripts/gemini_acceptance_smoke.py --execute --json` still needs one real Vertex AI acceptance run after the doctor passes.
- Historical full-suite failures/errors still need systematic triage after the repository can be executed locally.

## Single best next step

**Refactor `scripts/gcp_deploy_doctor.py` to import and use `gcp_identifiers.py` for `PROJECT_ID`, `REGION`, `SERVICE_NAME`, and `IMAGE_URL`, then extend offline doctor parity tests so every identifier accepted/rejected by the production deploy helper receives the same result from the doctor. After that, add a read-only live Cloud Run region availability check rather than hard-coding a region list.**

## Retained production hardening

- Cloud Run production deployment uses authenticated GCS checkpoints rather than silent ephemeral/no-checkpoint state.
- Runtime checkpoint HMAC keys are Secret Manager supplied and at least 32 UTF-8 bytes.
- Checkpoint object validation is byte-accurate and aligned across deploy helper, deployment doctor, and runtime.
- Cloud Run deployment rejects malformed/injected comma-delimited environment and secret mapping inputs before `gcloud`.
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

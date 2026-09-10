# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the indispensable runtime evidence plane. The proven vertical slice remains intact: deterministic telemetry, Prometheus/Loki/Grafana, official read-only Grafana MCP access, bounded diagnosis, optional revision-bound Gemini briefing, exact human approval, safe remediation, Grafana-based recovery verification, authenticated lifecycle state, and a same-origin operator cockpit.

Core invariants remain unchanged:
- Grafana is the evidence plane; infrastructure write credentials stay isolated from Grafana/MCP access.
- Gemini is optional/advisory and cannot mutate diagnosis, approval, remediation, or recovery state.
- Human approval is single-use and bound to the exact evidence revision.
- Remediation success is never inferred from an action response; fresh Grafana telemetry must prove recovery.
- Local credentials/state remain under gitignored `.stageguard/` and `runtime/.secrets/` paths.
- Authenticated checkpointing, audit integrity, execution reconciliation, and no-replay protections remain implemented.

## Run log — 2026-09-10 — authenticated durable Cloud Run checkpoints

### Inspected at start

Read `progress.md` completely before choosing work, then inspected the repository root and the current production boundary in:
- `runtime/cloudrun_entrypoint.py`
- `runtime/bootstrap.py`
- `runtime/incident_checkpoint.py`
- `scripts/deploy_cloud_run.sh`
- `scripts/gcp_deploy_doctor.py`
- `runtime/tests/test_cloudrun_entrypoint.py`
- `runtime/tests/test_cloud_run_deploy_contract.py`
- `runtime/tests/test_gcp_deploy_doctor.py`
- `GOOGLE_CLOUD_DEPLOYMENT.md`

The runtime already had an authenticated `GoogleCloudStorageCheckpointStore` with HMAC verification and optimistic generation-based compare-and-swap. The Cloud Run entrypoint could select it if `STAGEGUARD_CHECKPOINT_BUCKET` was manually configured. However, the standard production deployment helper did not set a checkpoint bucket, object, or HMAC secret at all, so a normal Cloud Run deployment silently selected `--checkpoint-backend none` and therefore had no restart-durable authenticated incident checkpoint.

### Exact changes made

Updated `runtime/cloudrun_entrypoint.py`:
- added bounded GCS bucket-name validation before runtime construction;
- rejects uppercase/undersized/IP-like/double-dot/reserved Google-like bucket identifiers and malformed boundary characters;
- added bounded checkpoint object-path validation;
- rejects leading/trailing slash, empty path segments, `.`/`..` traversal segments, backslashes, commas, control characters, surrounding whitespace, and paths over 512 UTF-8 bytes;
- changed checkpoint object behavior to always pass the validated explicit/default object when GCS is enabled;
- validates `STAGEGUARD_CHECKPOINT_HMAC_KEY` is at least 32 UTF-8 bytes before bootstrap;
- rejects orphan object/HMAC configuration when no checkpoint bucket is configured;
- preserves the safe local/no-bucket fallback as `checkpoint-backend none` plus `allow_unbound_legacy`.

Updated `scripts/deploy_cloud_run.sh`:
- production deployment now requires `CHECKPOINT_BUCKET` and `CHECKPOINT_HMAC_SECRET`;
- added optional `CHECKPOINT_OBJECT`, defaulting to `stageguard/incident-checkpoint.json`;
- validates checkpoint bucket/object identifiers before invoking `gcloud run deploy`;
- forwards only the bucket/object identifiers as ordinary Cloud Run environment configuration;
- binds `STAGEGUARD_CHECKPOINT_HMAC_KEY` directly to the named Secret Manager secret via `--set-secrets`; the HMAC payload is never placed in `ENV_VARS` or shell interpolation;
- standard Cloud Run deployment therefore activates authenticated GCS checkpointing instead of silently running without durable incident state;
- production remediation remains disabled and no remediation credentials were added.

Updated `runtime/tests/test_cloudrun_entrypoint.py`:
- added short-HMAC rejection;
- added default object contract coverage;
- added invalid bucket-name cases;
- added path traversal/delimiter/control/backslash/object-boundary cases;
- added orphan checkpoint configuration rejection.

Updated `runtime/tests/test_cloud_run_deploy_contract.py`:
- asserts checkpoint bucket/HMAC secret are required production inputs;
- asserts the bucket/object are forwarded into the runtime;
- asserts HMAC payload resolution stays in Secret Manager rather than `ENV_VARS`;
- asserts checkpoint identifier validation occurs before `gcloud run deploy`.

Commits created this run:
- `681b47672a3490bdde03d61f3ed3d5af74c46c9a` — harden Cloud Run checkpoint configuration
- `b54569c9775019e46ac27e44b938420676b62b84` — test Cloud Run checkpoint boundary
- `5e2f3275e6e70f726a71ec9488c742a0e13f50cc` — wire authenticated GCS checkpoints into Cloud Run
- `113d4f3f982a71d1c50eaa718449a791eaaf3310` — cover durable checkpoint deployment contract

### Tests / checks / results

Source-level verification through the GitHub connector confirmed the committed deployment helper now requires and forwards the durable checkpoint configuration, while the runtime entrypoint validates it and the deployment contract tests assert that the HMAC payload is not placed in the ordinary environment-variable list.

Attempted a fresh public checkout and focused test run with:

```text
git clone --depth 1 https://github.com/UnknownGod2011/Grafana.git /tmp/stageguard
python -m unittest runtime.tests.test_cloudrun_entrypoint runtime.tests.test_cloud_run_deploy_contract
```

The execution container failed before checkout because DNS could not resolve `github.com`. Therefore the new focused tests were not empirically executed here and no green-suite claim is made.

No GitHub Actions workflow was created, triggered, or rerun. No Grafana instance, MCP server, Google Cloud resource, bucket, IAM policy, Secret Manager payload, Gemini endpoint, or remediation endpoint was modified.

### Decisions made

1. **Standard production deployment should not silently lose restart durability.** The deploy helper now requires authenticated GCS checkpoint configuration rather than relying on an operator to discover optional runtime variables.
2. **Checkpoint authenticity is independent of bucket IAM.** The HMAC secret stays in Secret Manager and the existing checkpoint store verifies checkpoint signatures before accepting restored state.
3. **Malformed identifiers fail before incident runtime construction.** The production entrypoint does not rely only on the deployment shell because other deployment mechanisms may call the container directly.
4. **The HMAC payload is never a literal deployment variable.** `--set-secrets` references only the Secret Manager resource name/version; the secret value is resolved by Cloud Run.
5. **No destructive cloud setup is automated here.** The helper consumes an existing bucket/secret and does not create buckets, secrets, or IAM grants.

### Current blockers / unknowns

- `scripts/gcp_deploy_doctor.py` does not yet include `CHECKPOINT_BUCKET`/`CHECKPOINT_HMAC_SECRET`, the Storage API, checkpoint bucket existence, HMAC-secret existence/access, or effective Cloud Storage object permissions. Until that is corrected, the doctor can theoretically report its older prerequisites as ready while the newly hardened deploy helper refuses to run.
- `GOOGLE_CLOUD_DEPLOYMENT.md` still needs to be updated to document the now-required durable checkpoint inputs and GCS IAM contract.
- The focused Cloud Run checkpoint tests and deployment-contract tests still need empirical execution from a runnable checkout.
- `runtime.tests.test_command_line`, MCP/readiness suites, `runtime.tests.test_gemini_acceptance_smoke`, and the full unittest suite still need empirical execution.
- `ENABLE_GEMINI=true python scripts/gcp_deploy_doctor.py --json` still needs a live authorized disposable GCP project.
- `python scripts/gemini_acceptance_smoke.py --execute --json` still needs one real authorized Vertex AI acceptance run after the doctor passes.
- Historical full-suite failures/errors still need systematic triage.

## Single best next step

**Bring `scripts/gcp_deploy_doctor.py` into exact parity with the hardened production deployment contract: require/validate `CHECKPOINT_BUCKET` and `CHECKPOINT_HMAC_SECRET`, require `storage.googleapis.com`, verify the bucket and HMAC secret exist without reading payloads, and use Policy Troubleshooter to fail closed unless the runtime service account has the exact Cloud Storage object permissions needed by the generation-based GCS checkpoint store. Then update `GOOGLE_CLOUD_DEPLOYMENT.md` with the resulting least-privilege IAM contract.**

## Retained production hardening

- Runtime MCP launcher parsing is centralized and cross-platform, preserving Windows paths while failing closed on malformed quoting.
- Readiness validates local activation/pin trust before spawning or querying Grafana MCP clients.
- `scripts/gcp_deploy_doctor.py` validates its existing deployment configuration, required APIs, runtime service account, Secret Manager resources/access, Cloud Logging permissions, conditional Vertex prediction permission, and image availability; offline validation cannot report deploy-ready. Its checkpoint parity is the next task.
- `scripts/gemini_acceptance_smoke.py` defaults to validation-only and requires explicit `--execute` for one bounded synthetic Vertex request.
- `scripts/deploy_cloud_run.sh` forwards the explicit Google Cloud project, location, Gemini model, IAP identity configuration, Secret Manager mounts, authenticated GCS checkpoint configuration, and keeps production remediation disabled.
- Operator/API safety continues to expose bounded incident/evidence/reconciliation state without raw queries or credentials.

## Validation baseline retained

- Local onboarding doctor: 8 tests passed, 1 expected platform-specific permission test skipped on Windows.
- Focused core/API/UI suite from the last executable run: 81/81 passed.
- Historical full suite baseline: 352 tests, 9 failures, 15 errors, 19 skipped; no full-suite green claim.
- Live Docker rehearsal: PASS twice consecutively.
- Official Grafana MCP read-only smoke path: PASS using `grafana/mcp-grafana:1.3.0`.
- Incident flow: investigate -> diagnose `uplink-b packet loss` -> exact revision approval -> bounded remediation -> telemetry-verified recovered.
- Gemini integration is implemented; live production authorization/inference acceptance remains pending an authorized disposable GCP environment.

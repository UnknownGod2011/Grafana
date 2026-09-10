# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the indispensable runtime evidence plane. The working vertical slice remains: deterministic telemetry, Prometheus/Loki/Grafana, official read-only Grafana MCP access, bounded diagnosis, optional revision-bound Gemini briefing, exact human approval, safe remediation, Grafana-based recovery verification, authenticated lifecycle state, restart reconciliation, and a same-origin operator cockpit.

Core invariants remain unchanged:
- Grafana is the evidence plane; infrastructure write credentials stay isolated from Grafana/MCP access.
- Gemini is optional/advisory and cannot mutate diagnosis, approval, remediation, or recovery state.
- Human approval is single-use and bound to the exact evidence revision.
- Remediation success is never inferred from an action response; fresh Grafana telemetry must prove recovery.
- Authenticated checkpoints and audit integrity fail closed.

## Run log — 2026-09-10 — durable checkpoint deployment preflight parity

### Inspected at start

Read `progress.md` completely before choosing work. Then inspected:
- `scripts/gcp_deploy_doctor.py`
- `scripts/deploy_cloud_run.sh`
- `runtime/cloudrun_entrypoint.py`
- `runtime/incident_checkpoint.py`
- `runtime/tests/test_gcp_deploy_doctor.py`
- `runtime/tests/test_cloud_run_deploy_contract.py`
- `runtime/tests/test_cloudrun_entrypoint.py`
- `GOOGLE_CLOUD_DEPLOYMENT.md`

The previous run had made authenticated GCS checkpointing mandatory in the standard Cloud Run deployment, but the deployment doctor still reflected the older contract. It could therefore report its old prerequisites as ready while the deploy helper required additional checkpoint inputs and runtime GCS permissions.

### Research / runtime contract confirmed

Reviewed current Google Cloud documentation for Cloud Storage object permissions and full resource names. The implemented `GoogleCloudStorageCheckpointStore` performs metadata/data reads and generation-preconditioned writes to one object. Google documents:
- `storage.objects.get` for reading object data/metadata;
- `storage.objects.create` for upload/create;
- `storage.objects.delete` when an upload overwrites an existing object;
- Cloud Storage object full resource names as `//storage.googleapis.com/projects/_/buckets/BUCKET/objects/OBJECT`.

StageGuard runtime therefore does not need object listing or bucket administration for checkpoint operation.

### Exact changes made

Updated `scripts/gcp_deploy_doctor.py`:
- added mandatory `CHECKPOINT_BUCKET` and `CHECKPOINT_HMAC_SECRET` deployment inputs;
- added `storage.googleapis.com` to the required APIs;
- added `CHECKPOINT_HMAC_SECRET` to Secret Manager existence/access verification without reading payloads;
- added bounded checkpoint bucket validation aligned with the Cloud Run entrypoint;
- added bounded checkpoint object validation, defaulting to `stageguard/incident-checkpoint.json`;
- added read-only bucket metadata existence/access verification via `gcloud storage buckets describe`;
- added fail-closed IAM Policy Troubleshooter checks for the exact runtime permissions `storage.objects.get`, `storage.objects.create`, and `storage.objects.delete`;
- scopes those checks to the exact configured Cloud Storage object full resource name;
- exposes resolved checkpoint bucket/object in JSON output;
- adds least-privilege remediation guidance and explicitly states that list/bucket-admin permissions are not required by StageGuard runtime.

Updated `runtime/tests/test_gcp_deploy_doctor.py`:
- updated the canonical valid deployment environment with checkpoint inputs;
- added offline failures for missing checkpoint bucket/HMAC-secret inputs;
- added invalid bucket/object boundary cases;
- asserts Storage API presence;
- asserts the exact three storage runtime permissions;
- asserts exact Cloud Storage object resource construction;
- covers denied/unknown Policy Troubleshooter states and command/JSON failures;
- preserves regression coverage for Secret Manager, Cloud Logging, Gemini/Vertex, image, service-account, project-number, and Grafana URL contracts.

Updated `GOOGLE_CLOUD_DEPLOYMENT.md`:
- documents authenticated GCS checkpoint configuration and HMAC handling;
- documents exact runtime object operations and least-privilege IAM permissions;
- documents the Policy Troubleshooter object resource path and underscore project placeholder;
- updates the deployment helper environment contract;
- updates doctor behavior, failure modes, and official references.

Commits created this run:
- `aebbab227f2b6b7743b71a6840fd6c2403d60c8b` — harden deploy doctor for durable GCS checkpoints
- `df64438c9bb5844c41e2382e35f91e85549a5396` — cover durable checkpoint deployment preflight
- `e2c426d46d260b5a9b0b4afe84027d17b81b011a` — document durable checkpoint IAM contract

### Tests / checks / results

Attempted a fresh checkout and focused run:

```text
git clone --depth 1 https://github.com/UnknownGod2011/grafana.git /tmp/stageguard
python -m unittest runtime.tests.test_gcp_deploy_doctor runtime.tests.test_cloud_run_deploy_contract runtime.tests.test_cloudrun_entrypoint
```

The execution container failed before checkout because DNS could not resolve `github.com`. Therefore the focused suite was not empirically executed here and no green-suite claim is made.

Source-level verification through the GitHub connector confirmed the committed doctor now includes the checkpoint deployment inputs, Storage API, HMAC secret, bucket check, and exact object permission checks.

No GitHub Actions workflow was created, triggered, or rerun. No Grafana instance, MCP server, GCP project, bucket, object, IAM policy, Secret Manager payload, Gemini endpoint, or remediation endpoint was modified.

### Decisions made

1. Runtime checkpoint permissions are `storage.objects.get/create/delete`; no list or bucket-admin permission is required.
2. Effective access is checked rather than assuming role names. `roles/storage.objectUser` is documented only as a standard predefined option.
3. The doctor never reads checkpoint or secret payloads and never exercises write permissions; it uses metadata lookup plus Policy Troubleshooter.
4. Checkpoint bucket/object syntax is validated before any live storage permission proof.
5. Standard production deployment remains remediation-disabled.

### Current blockers / unknowns

- The focused doctor/deployment/entrypoint tests still need empirical execution from a runnable checkout.
- The exact Cloud Storage object Policy Troubleshooter tuple still needs one authorized disposable-project acceptance run.
- `ENABLE_GEMINI=true python scripts/gcp_deploy_doctor.py --json` still needs a live authorized disposable GCP project.
- `python scripts/gemini_acceptance_smoke.py --execute --json` still needs one real Vertex AI acceptance run after the doctor passes.
- Historical full-suite failures/errors still need systematic triage after focused production-boundary tests can run.

## Single best next step

**Run the updated doctor against an authorized disposable Google Cloud project with a dedicated checkpoint bucket and runtime service account, first with one storage permission intentionally missing and then with the exact `storage.objects.get/create/delete` set. Confirm Policy Troubleshooter accepts the exact Cloud Storage object full-resource name and that `ready_to_deploy` fails closed until all three permissions and the checkpoint HMAC-secret access are effective.**

## Retained production hardening

- Cloud Run production deployment uses authenticated GCS checkpoints rather than silent ephemeral/no-checkpoint state.
- Runtime checkpoint HMAC keys are Secret Manager supplied and at least 32 UTF-8 bytes.
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

# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the indispensable runtime evidence and observability plane. The proven core vertical slice remains intact: deterministic broadcast telemetry, Prometheus/Grafana, official read-only Grafana MCP access, bounded diagnosis, optional revision-bound Gemini briefing, explicit human approval, safe remediation, Grafana-based recovery verification, authenticated lifecycle state, and a same-origin operator cockpit.

The repository is in productization mode. Current priorities are real Grafana Cloud/self-hosted onboarding, production Google Cloud deployment, testability, maintainability, and operational safety.

Core invariants:

- Grafana is the evidence plane; infrastructure write credentials stay isolated from Grafana/MCP access.
- Gemini is optional/advisory and cannot mutate approval, remediation, or recovery state.
- Human approval is single-use and bound to the exact evidence revision.
- Remediation success is never inferred from an action response; fresh Grafana telemetry must prove recovery.
- Local credentials/state remain under gitignored `.stageguard/` and `runtime/.secrets/` paths.
- Authenticated checkpointing, audit integrity, execution reconciliation, and no-replay protections remain implemented.

## Run log — 2026-09-10 — conditional Vertex AI runtime authorization gate

### Inspected at start

Read `progress.md` completely before choosing work. Inspected:

- `scripts/gcp_deploy_doctor.py`
- `runtime/tests/test_gcp_deploy_doctor.py`
- retained Cloud Run/Gemini environment contract from `scripts/deploy_cloud_run.sh`
- prior Secret Manager and Cloud Logging Policy Troubleshooter gates

The previous single best next step was directly actionable, so this run implemented it rather than widening architecture scope.

### Official documentation checked

Current Google Cloud documentation was checked before changing the deployment contract:

- Vertex AI `generateContent` uses a publisher-model resource formatted as `projects/{project}/locations/{location}/publishers/*/models/*`.
- Google Gemini publisher requests use the `:generateContent` path; the global route uses `locations/global`.
- Runtime inference requires `aiplatform.endpoints.predict`.
- Google documents `roles/aiplatform.user` as the standard predefined role that includes the prediction permission, while StageGuard continues to gate the underlying permission rather than requiring that broad role by name.

References:

- https://docs.cloud.google.com/workflows/docs/reference/googleapis/aiplatform/v1/projects.locations.endpoints/generateContent
- https://docs.cloud.google.com/workflows/docs/tutorials/use-vertex-ai-models
- https://docs.cloud.google.com/gemini-enterprise-agent-platform/machine-learning/general/iam-permissions
- https://docs.cloud.google.com/gemini-enterprise-agent-platform/resources/locations

### Exact changes made

Updated `scripts/gcp_deploy_doctor.py`:

- added `VERTEX_PREDICT_PERMISSION = "aiplatform.endpoints.predict"`;
- resolved Gemini runtime location/model with the same deployment defaults already used by StageGuard:
  - `GOOGLE_CLOUD_LOCATION=global` by default;
  - `STAGEGUARD_GEMINI_MODEL=gemini-2.5-flash` by default;
- added syntax validation for the optional location/model identifiers when Gemini is enabled, rejecting URLs/resource paths before deployment;
- added `_vertex_predict_access_check(...)`, which asks IAM Policy Troubleshooter about the exact configured publisher-model full resource:
  `//aiplatform.googleapis.com/projects/PROJECT_ID/locations/LOCATION/publishers/google/models/MODEL`;
- made the Vertex permission proof conditional on `ENABLE_GEMINI=true`; Gemini-disabled deployments do not acquire this extra IAM requirement;
- reused the existing fail-closed Troubleshooter semantics: denied, unknown, malformed JSON, empty output, or command failure all block readiness;
- kept the check read-only: it does not invoke the model, alter IAM, enable APIs, or mutate cloud resources;
- exposed the resolved Gemini location/model in JSON doctor output for deployment debugging;
- added actionable remediation guidance naming `aiplatform.endpoints.predict`, while explicitly allowing a narrower custom/inherited grant instead of forcing `roles/aiplatform.user`.

Updated `runtime/tests/test_gcp_deploy_doctor.py`:

- locks the exact Vertex runtime permission contract;
- verifies the exact publisher-model Policy Troubleshooter resource shape for the default global Gemini path;
- verifies runtime service-account principal and permission arguments;
- covers CAN_ACCESS, CANNOT_ACCESS, UNKNOWN, command failure, and invalid JSON;
- verifies remediation guidance includes the required permission;
- verifies Gemini runtime defaults in offline JSON output;
- verifies malformed location/model values fail before live deployment;
- retained existing Secret Manager, Cloud Logging, API, and offline readiness coverage.

Commits created this run:

- `07cad996136f69a6c3880da0d6ae1f6fec19c254` — conditional Vertex AI runtime permission gate
- `cca40b3388cea04d80868562e5f6945c8137e90f` — Vertex permission and configuration regression coverage

### Tests / checks / results

- Source-level review completed for the new Gemini location/model resolution, publisher-model full resource, conditional live gate, JSON output, and next-step remediation.
- Attempted to obtain a fresh executable checkout using `git clone`; this execution container still cannot resolve `github.com`, so empirical local execution was blocked before Python could run.
- No PASS claim is made for the newly expanded test module.
- No GitHub Actions workflow was added, triggered, or rerun.
- No Google Cloud resource, IAM policy, API, secret, Grafana instance, Gemini endpoint, or remediation endpoint was modified.

### Decisions made

1. **Gate the runtime permission, not a role name.** StageGuard checks effective `aiplatform.endpoints.predict`; inherited/custom least-privilege IAM remains valid.
2. **Make Gemini IAM conditional.** `ENABLE_GEMINI=false` retains the smaller runtime authorization surface.
3. **Use the publisher-model resource StageGuard actually calls.** The preflight target mirrors the documented `projects/{project}/locations/{location}/publishers/google/models/{model}:generateContent` path.
4. **Fail closed on IAM uncertainty.** An indeterminate Troubleshooter result cannot produce `ready_to_deploy=true`.
5. **Keep the doctor read-only.** It verifies authorization without making a paid/model inference request or altering access.

### Current blockers / unknowns

- The expanded `runtime.tests.test_gcp_deploy_doctor` suite still needs empirical execution on a checkout with working GitHub/DNS access.
- A disposable authorized Google Cloud project is still needed to confirm that Policy Troubleshooter accepts the publisher-model full resource exactly as constructed and returns the expected `overallAccessState` contract.
- Gemini/Vertex production acceptance still requires a real authorized `generateContent` call after the read-only IAM gate passes.
- Historical broader-suite failures/errors still need systematic triage.

## Single best next step

**Run `python scripts/gcp_deploy_doctor.py --json` in a disposable authorized Google Cloud project with `ENABLE_GEMINI=true` and verify the live Policy Troubleshooter result for `//aiplatform.googleapis.com/projects/PROJECT_ID/locations/LOCATION/publishers/google/models/MODEL`; once that read-only gate is empirically confirmed, add a separate opt-in Gemini acceptance smoke test that performs one minimal `generateContent` call without changing StageGuard state.**

## Retained production hardening

### Google Cloud deployment doctor

`scripts/gcp_deploy_doctor.py` now validates:

- required deployment environment syntax;
- active `gcloud` identity;
- `PROJECT_ID` / `PROJECT_NUMBER` consistency;
- required APIs, with Vertex AI conditional on `ENABLE_GEMINI=true`;
- runtime service-account existence;
- mounted Secret Manager resource existence without payload reads;
- effective `secretmanager.versions.access` for every mounted secret through Policy Troubleshooter;
- effective `logging.logEntries.create` and `logging.logEntries.list` for the runtime service account;
- conditional effective `aiplatform.endpoints.predict` on the configured Gemini publisher-model path;
- Artifact Registry image availability.

Offline syntax validation can never report `ready_to_deploy=true`.

### Cloud Run / Vertex runtime contract

`scripts/deploy_cloud_run.sh` explicitly forwards:

- `GOOGLE_CLOUD_PROJECT=${PROJECT_ID}`;
- optional `GOOGLE_CLOUD_LOCATION` (default `global`);
- optional `STAGEGUARD_GEMINI_MODEL` (default `gemini-2.5-flash`).

The standard Cloud Run artifact exposes no production-remediation switch or write credential.

### Production onboarding doctor

`scripts/stageguard_doctor.py` validates Python 3.11+, strict telemetry mapping, `GRAFANA_URL`, token-file presence/non-emptiness/permissions without reading token contents, Grafana MCP launcher discovery, and optional activation-file presence. `runtime/preflight.py` remains authoritative for live Grafana/MCP evidence acceptance.

### Operator cockpit

The cockpit surfaces incident state, root cause, confidence, evidence revision, human approval, Grafana MCP provenance, and the `ACTION ACCEPTED ≠ INCIDENT RESOLVED` recovery-verification sequence. Bounded lifecycle responses expose provider, read-only status, datasource UID, query/recovery counts, and tool latency while excluding raw queries and secrets.

### Cross-platform persistence

Windows checkpoint/retention persistence avoids unavailable `os.fchmod`, invalid fsync behavior on read-only handles, and unsupported directory-fsync assumptions.

## Validation baseline retained

- Local onboarding doctor: 8 tests passed, 1 expected platform-specific permission test skipped on Windows.
- Focused core/API/UI suite from the last executable run: 81/81 passed.
- Historical full suite baseline: 352 tests, 9 failures, 15 errors, 19 skipped; no full-suite green claim.
- Live Docker rehearsal: PASS twice consecutively.
- Official Grafana MCP read-only smoke path: PASS using `grafana/mcp-grafana:1.3.0`.
- Incident flow: investigate → diagnose `uplink-b packet loss` → exact revision approval → bounded remediation → telemetry-verified recovered.
- Gemini: integration implemented but not exercised in the last local capture because credentials were unavailable.

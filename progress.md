# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the runtime evidence and observability plane. The proven core vertical slice remains intact: deterministic broadcast telemetry, Prometheus/Grafana, official read-only Grafana MCP access, bounded diagnosis, optional revision-bound Gemini briefing, explicit human approval, safe remediation, Grafana-based recovery verification, authenticated lifecycle state, and a same-origin operator cockpit.

The repository is in productization mode. Current priorities are real Grafana Cloud/self-hosted onboarding, production Google Cloud deployment, testability, maintainability, and operational safety.

Core invariants:

- Grafana is the evidence plane; infrastructure write credentials stay isolated from Grafana/MCP access.
- Gemini is optional/advisory and cannot mutate approval, remediation, or recovery state.
- Human approval is single-use and bound to the exact evidence revision.
- Remediation success is never inferred from an action response; fresh Grafana telemetry must prove recovery.
- Local credentials/state remain under gitignored `.stageguard/` and `runtime/.secrets/` paths.
- Authenticated checkpointing, audit integrity, execution reconciliation, and no-replay protections remain implemented.

## Run log — 2026-09-10 — Cloud Run Vertex runtime contract

### Inspected at start

Read `progress.md` completely before choosing work. Inspected the current Google Cloud production boundary in:

- `scripts/gcp_deploy_doctor.py`
- `scripts/deploy_cloud_run.sh`
- `runtime/cloudrun_entrypoint.py`
- `runtime/bootstrap.py`
- `runtime/gemini_commander.py`
- `runtime/cloud_audit.py`
- `runtime/durable_audit_reader.py`
- `runtime/tests/test_gcp_deploy_doctor.py`
- `GOOGLE_CLOUD_DEPLOYMENT.md`

The previous best next step requires a disposable authorized Google Cloud project, which is not available in this execution environment. I therefore worked the highest-value unblocked production defect rather than stopping.

### Concrete defect found

`ENABLE_GEMINI=true` was forwarded by the Cloud Run deploy helper, but `GOOGLE_CLOUD_PROJECT` was not. `GoogleGenAICommanderModel.from_vertex_ai_environment()` explicitly refuses to initialize without `GOOGLE_CLOUD_PROJECT`. This meant a Cloud Run deployment could succeed while the optional Gemini commander failed at runtime solely because the deployment helper omitted a required non-secret environment variable.

A second production requirement was clarified while reviewing the audit path: StageGuard uses Cloud Logging for both bounded audit appends and restart/reconciliation reads. The runtime therefore needs `logging.logEntries.create` **and** `logging.logEntries.list`; writer-only IAM guidance was incomplete.

### Official documentation checked

Current Google Cloud documentation was checked before changing the deployment contract:

- IAM Policy Troubleshooter project resource names use `//cloudresourcemanager.googleapis.com/projects/...`.
- Cloud Logging `entries.write` requires `logging.logEntries.create`.
- Cloud Logging read/list operations require `logging.logEntries.list` for ordinary log entries.
- Vertex AI generative prompt requests require `aiplatform.endpoints.predict`.

References:

- https://cloud.google.com/policy-intelligence/docs/troubleshoot-access
- https://cloud.google.com/logging/docs/reference/v2/rest/v2/entries/write
- https://cloud.google.com/iam/docs/roles-permissions/logging
- https://cloud.google.com/vertex-ai/generative-ai/docs/access-control

### Exact changes made

Updated `scripts/deploy_cloud_run.sh`:

- always forwards `GOOGLE_CLOUD_PROJECT=${PROJECT_ID}` to the Cloud Run container;
- forwards optional `GOOGLE_CLOUD_LOCATION`, defaulting to `global`;
- forwards optional `STAGEGUARD_GEMINI_MODEL`, defaulting to `gemini-2.5-flash`;
- validates location/model values are non-empty and contain no commas or whitespace before placing them in `--set-env-vars`;
- preserves Secret Manager file mounts and the no-production-remediation boundary.

Added `runtime/tests/test_cloud_run_deploy_contract.py`:

- locks the deploy/runtime contract for `GOOGLE_CLOUD_PROJECT`;
- locks location/model defaults against `runtime/gemini_commander.py`;
- checks delimiter-injection guards remain present;
- verifies the standard deploy helper still exposes no production-remediation environment variables;
- verifies the Grafana service-account token remains a Secret Manager file mount rather than a plaintext environment variable.

Updated `GOOGLE_CLOUD_DEPLOYMENT.md`:

- documents the explicit Vertex project/location/model environment contract;
- explains why the deployment helper forwards `GOOGLE_CLOUD_PROJECT`;
- corrects Cloud Logging IAM guidance to include both lifecycle writes and restart-safe reads;
- records the underlying logging permissions and the remaining production-preflight hardening work;
- updates failure behavior and official references.

Commits created this run:

- `7f933a93e5b6adf1b7c8ba86dde9b8df2f011bea` — propagate Vertex AI runtime configuration in Cloud Run deploy
- `ef330cba8554f210e8f1c996af562cc7ef9c0531` — lock Cloud Run Gemini deployment contract
- `519d3b202ddd6a35efc21e38574c9292e092fd49` — document Vertex runtime environment and Cloud Logging read IAM

### Tests / checks / results

- Source-level contract review completed across deploy helper, Cloud Run entrypoint, bootstrap, Gemini adapter, Cloud Logging sink, and audit reader.
- Attempted a fresh shallow checkout to run `runtime.tests.test_cloud_run_deploy_contract` and `runtime.tests.test_gcp_deploy_doctor`; the execution sandbox could not resolve `github.com`, so the checkout failed before Python ran.
- No PASS claim is made for the newly added test module.
- No GitHub Actions workflow was added or triggered.
- No Google Cloud resource, IAM policy, API, secret, Grafana instance, Gemini endpoint, or remediation endpoint was modified.

### Decisions made

1. **Fix explicit runtime configuration rather than rely on ambient Cloud Run behavior.** The Gemini adapter requires `GOOGLE_CLOUD_PROJECT`; the deploy helper now guarantees it.
2. **Keep Gemini location/model configurable but bounded.** Operators can choose a supported location/model without editing the script, while comma/whitespace guards protect the comma-delimited `--set-env-vars` composition.
3. **Do not grant or mutate IAM automatically.** Documentation now states the real logging permissions; effective-permission gates should be added only after validating the Policy Troubleshooter response contract in a disposable project.
4. **Keep the standard Cloud Run artifact read-only with respect to remediation.** No remediation endpoint/token/switch was introduced.

### Current blockers / unknowns

- The new deploy-contract tests still need empirical execution on an executable checkout.
- A real Google Cloud acceptance run is still needed to confirm Policy Troubleshooter behavior for all four Secret Manager secrets.
- Effective runtime checks for `logging.logEntries.create`, `logging.logEntries.list`, and (when Gemini is enabled) `aiplatform.endpoints.predict` are not yet deployment gates.
- Gemini/Vertex AI production acceptance still requires a real authorized project/model call.
- Historical broader-suite failures/errors still need systematic triage.

## Single best next step

**Extend `scripts/gcp_deploy_doctor.py` with fail-closed, read-only IAM Policy Troubleshooter checks for the runtime service account's `logging.logEntries.create` and `logging.logEntries.list` permissions on the target project, add credential-free response-contract tests, and only then consider the conditional Vertex `aiplatform.endpoints.predict` gate after its target resource shape is validated against a real Gemini project.**

## Previous production hardening — effective Secret Manager authorization

The Google Cloud deployment doctor already:

- requires `policytroubleshooter.googleapis.com` for live preflight;
- verifies each mounted Secret Manager resource exists without reading payloads;
- checks the runtime service account's effective `secretmanager.versions.access` permission using IAM Policy Troubleshooter;
- treats `CAN_ACCESS` as success and denied/unknown/malformed/command-failure states as deployment blockers;
- dynamically requires `aiplatform.googleapis.com` when `ENABLE_GEMINI=true`;
- keeps offline syntax validation from ever reporting `ready_to_deploy=true`.

Relevant commits retained:

- `f97be6537a09dc9e1e3dc90ab22a24f97101f83f` — effective Secret Manager runtime access verification
- `9411f6a6f36dd484dcd2f359f276d4badf9ebed4` — credential-free permission-check regression coverage

## Validation baseline retained

- Local onboarding doctor: 8 tests passed, 1 expected platform-specific permission test skipped on Windows.
- Focused core/API/UI suite from the last executable run: 81/81 passed.
- Historical full suite baseline: 352 tests, 9 failures, 15 errors, 19 skipped; no full-suite green claim.
- Live Docker rehearsal: PASS twice consecutively.
- Official Grafana MCP read-only smoke path: PASS using `grafana/mcp-grafana:1.3.0`.
- Incident flow: investigate → diagnose `uplink-b packet loss` → exact revision approval → bounded remediation → telemetry-verified recovered.
- Gemini: integration implemented but not exercised in the last local capture because credentials were unavailable.

## Recent productization milestones retained

### Google Cloud deployment doctor

`scripts/gcp_deploy_doctor.py` validates deployment environment syntax, active gcloud identity, project-number consistency, required APIs, runtime service-account existence, mounted Secret Manager resources, effective runtime secret-version permission, and Artifact Registry image availability. `ENABLE_GEMINI=true` dynamically requires Vertex AI. Offline syntax checks never authorize deployment.

### Production onboarding doctor

`scripts/stageguard_doctor.py` validates Python 3.11+, strict telemetry mapping, `GRAFANA_URL`, token-file presence/non-emptiness/permissions without reading token contents, Grafana MCP launcher discovery, and optional activation-file presence. `runtime/preflight.py` remains authoritative for live Grafana/MCP evidence acceptance.

### Operator cockpit

The cockpit surfaces incident state, root cause, confidence, evidence revision, human approval, Grafana MCP provenance, and the `ACTION ACCEPTED ≠ INCIDENT RESOLVED` recovery-verification sequence. Bounded lifecycle responses expose provider, read-only status, datasource UID, query/recovery counts, and tool latency while excluding raw queries and secrets.

### Cross-platform persistence

Windows checkpoint/retention persistence avoids unavailable `os.fchmod`, invalid fsync behavior on read-only handles, and unsupported directory-fsync assumptions.

### Live release rehearsal

A Windows Docker Desktop Linux-engine rehearsal passed healthy evidence gates, official Grafana MCP smoke validation, real fault gates, diagnosis, exact revision approval, bounded recovery, and post-action telemetry verification twice consecutively. Grafana Explore showed the packet-loss fault plateau returning to baseline.

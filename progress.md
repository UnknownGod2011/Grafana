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

## Run log — 2026-09-10 — effective Cloud Logging IAM deployment gate

### Inspected at start

Read `progress.md` completely before choosing work. Inspected:

- `scripts/gcp_deploy_doctor.py`
- `runtime/tests/test_gcp_deploy_doctor.py`
- `GOOGLE_CLOUD_DEPLOYMENT.md`
- the retained Cloud Run/Gemini deployment contract and prior Secret Manager Policy Troubleshooter gate

The prior single best next step was directly actionable without mutating cloud resources, so this run implemented it rather than widening scope.

### Official documentation checked

Current Google Cloud documentation was re-checked before changing the preflight contract:

- Policy Troubleshooter accepts a service-account principal, full resource name, and underlying IAM permission.
- A project resource is addressed as `//cloudresourcemanager.googleapis.com/projects/PROJECT_ID`.
- Cloud Logging `entries.write` requires `logging.logEntries.create`.
- Cloud Logging `entries.list` requires `logging.logEntries.list` for ordinary log entries.

References:

- https://cloud.google.com/policy-intelligence/docs/troubleshoot-access
- https://cloud.google.com/logging/docs/reference/v2/rest/v2/entries/write
- https://cloud.google.com/logging/docs/reference/v2/rest/v2/entries/list
- https://cloud.google.com/iam/docs/roles-permissions/logging

### Exact changes made

Updated `scripts/gcp_deploy_doctor.py`:

- added the exact production audit permission contract:
  - `logging.logEntries.create`
  - `logging.logEntries.list`
- factored Policy Troubleshooter result handling into one fail-closed `_troubleshoot_permission(...)` helper so Secret Manager and Logging checks share identical `CAN_ACCESS` / `CANNOT_ACCESS` / unknown / malformed / command-failure semantics;
- preserved the Secret Manager proof without reading any secret version payload;
- added `_logging_access_check(...)` using the target project full resource name and runtime service-account principal;
- only attempts IAM proofs after the configured runtime service account is confirmed to exist and the project lookup succeeds;
- makes both Logging permissions mandatory deployment checks, so a live doctor cannot report `ready_to_deploy=true` when StageGuard would be unable to append lifecycle audit or read it during restart/reconciliation;
- added actionable remediation text that names both required Logging permissions without mutating IAM;
- corrected the Logging resource identifier to use `PROJECT_ID` rather than the numeric project number after reviewing the official resource shape;
- retained the existing Artifact Registry failure detail and all prior no-secret/no-IAM-mutation behavior.

Updated `runtime/tests/test_gcp_deploy_doctor.py`:

- locks the exact two-permission Cloud Logging runtime contract;
- verifies Policy Troubleshooter receives `//cloudresourcemanager.googleapis.com/projects/stageguard-test`;
- verifies the runtime service-account principal and exact permission flag;
- covers allowed, denied, unknown, command-failure, and invalid-JSON outcomes;
- verifies denied/indeterminate states fail closed;
- verifies remediation guidance contains both `logging.logEntries.create` and `logging.logEntries.list`;
- retained all existing offline, Gemini API, and Secret Manager access tests.

Commits created this run:

- `7d6f6a8726ab765806721397b93c7a1458f8ca4c` — initial Cloud Logging IAM gate
- `b7768ab0467c7246e301a1190eee4fc68ba71554` — credential-free Logging permission tests
- `6e8338a5cdeeb378ba6603f5a066b3a4eaa65f4f` — correct Logging project resource to PROJECT_ID
- `dc9739ba856aa5b1a511f4e170198da0ab388bb2` — align tests with project-ID resource contract

### Tests / checks / results

- Source-level review completed for the new IAM helper, Secret Manager wrapper, Logging wrapper, live preflight integration, and next-step generation.
- Attempted to download the exact committed doctor/test files and run `py_compile` plus `python -m unittest runtime.tests.test_gcp_deploy_doctor -v` in the execution container.
- The container could not resolve `raw.githubusercontent.com`, so the executable validation attempt failed before Python ran.
- No PASS claim is made for the newly added tests.
- No GitHub Actions workflow was added or triggered.
- No Google Cloud resource, IAM policy, API, secret, Grafana instance, Gemini endpoint, or remediation endpoint was modified.

### Decisions made

1. **Gate underlying permissions, not role names.** Custom/inherited IAM can satisfy the runtime contract; the doctor checks effective permissions instead of requiring broad predefined roles.
2. **Fail closed on indeterminate IAM.** `UNKNOWN`, malformed Policy Troubleshooter output, command failure, or denied access all block deployment readiness.
3. **Keep authorization verification read-only.** The doctor never calls Cloud Logging write/list itself and never grants IAM; Policy Troubleshooter evaluates effective access only.
4. **Use project ID for the Cloud Logging resource.** This matches the documented project resource and the resource name used by `entries.list`.
5. **Do not add the Vertex permission gate yet.** `aiplatform.endpoints.predict` remains the next candidate only after its correct Policy Troubleshooter target resource shape is validated for the Gemini/Vertex path StageGuard actually uses.

### Current blockers / unknowns

- The expanded `runtime.tests.test_gcp_deploy_doctor` suite still needs empirical execution on a checkout with working GitHub/DNS access.
- A disposable authorized Google Cloud project is still needed to validate the live Policy Troubleshooter response contract for Secret Manager and both Logging permissions end-to-end.
- Conditional effective authorization for Gemini (`aiplatform.endpoints.predict`) is not yet a deployment gate.
- Gemini/Vertex AI production acceptance still requires a real authorized project/model call.
- Historical broader-suite failures/errors still need systematic triage.

## Single best next step

**Validate the correct Policy Troubleshooter resource target for StageGuard's actual Vertex/Gemini `aiplatform.endpoints.predict` call path using current official Vertex AI resource semantics, then add a conditional fail-closed permission gate only when `ENABLE_GEMINI=true`, with credential-free response-contract tests.**

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

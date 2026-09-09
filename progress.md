# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the runtime evidence and observability plane. The core vertical slice is implemented and has been exercised locally: deterministic broadcast telemetry, Prometheus/Grafana, official read-only Grafana MCP access, bounded diagnosis, optional revision-bound Gemini briefing, explicit human approval, safe remediation, Grafana-based recovery verification, authenticated lifecycle state, and a same-origin operator cockpit.

The repository is in productization mode. Preserve the proven incident flow while prioritizing real Grafana Cloud/self-hosted onboarding, production deployment, testability, maintainability, and operational safety.

Core invariants:

- Grafana is the evidence plane; infrastructure write credentials stay isolated from Grafana/MCP access.
- Gemini is optional/advisory and cannot mutate approval, remediation, or recovery state.
- Human approval is single-use and bound to the exact evidence revision.
- Remediation success is never inferred from an action response; fresh Grafana telemetry must prove recovery.
- Local credentials/state remain under gitignored `.stageguard/` and `runtime/.secrets/` paths.
- Authenticated checkpointing, audit integrity, execution reconciliation, and no-replay protections remain implemented.

## Run log — 2026-09-09 — Gemini deployment prerequisite alignment

### Inspected at start

Read `progress.md` completely, then inspected `scripts/gcp_deploy_doctor.py`, `scripts/deploy_cloud_run.sh`, and `runtime/tests/test_gcp_deploy_doctor.py`. The highest-value defect found was a mismatch between the deployment helper and its doctor: `deploy_cloud_run.sh` accepts and acts on `ENABLE_GEMINI`, but the doctor neither validated that value nor required Vertex AI when Gemini was enabled. That meant a configuration could be reported as deployment-ready even though the actual Gemini-enabled runtime path would fail.

### Exact changes made

Updated `scripts/gcp_deploy_doctor.py` so that it now:

- parses `ENABLE_GEMINI` using the same accepted true/false aliases as `scripts/deploy_cloud_run.sh`;
- fails preflight on invalid values instead of allowing deployment to discover the error later;
- reports the resolved Gemini state in JSON output;
- computes required Google Cloud APIs dynamically;
- requires `aiplatform.googleapis.com` when `ENABLE_GEMINI=true`;
- keeps Vertex AI optional when Gemini is disabled;
- gives a targeted remediation step when Gemini configuration or required APIs are missing.

Updated `runtime/tests/test_gcp_deploy_doctor.py` with credential-free coverage for:

- Gemini disabled by default in the deployment fixture;
- Vertex AI omitted from required APIs when Gemini is disabled;
- Vertex AI included when Gemini is enabled;
- boolean aliases matching the deployment helper (`1/0`, `true/false`, `yes/no`, `on/off`, case-insensitive);
- invalid Gemini values causing an offline preflight failure before deployment.

Commits created by the file updates:

- `8394d2997546d7fd67c82e2a7d0ae7d66973ff0c` — Gemini-aware deployment doctor
- `c9812da0f8206882c4195ac3207d77c679e0b29c` — Gemini deployment-doctor regression coverage

### Tests / checks / results

- Performed source-level consistency review between the updated doctor and `deploy_cloud_run.sh`.
- Attempted a fresh public GitHub checkout to execute `python -m unittest runtime.tests.test_gcp_deploy_doctor -v`; the execution environment could not resolve `github.com`, so the checkout failed before any tests ran.
- No PASS claim is made for the updated test module in this run.
- No GitHub Actions workflow was added or triggered.
- No Google Cloud project, IAM policy, API, secret payload, Grafana instance, Gemini endpoint, or remediation endpoint was changed.

### Decisions made

1. **The deploy doctor must model the deployment helper exactly.** Optional flags that alter runtime prerequisites cannot remain invisible to preflight.
2. **Gemini remains optional, but enabling it must be fail-closed.** StageGuard may deploy without Gemini; if Gemini is explicitly enabled, Vertex AI availability becomes a required deployment condition.
3. **Keep preflight non-mutating.** Missing Vertex AI is reported; the doctor never enables the API itself.
4. **Do not broaden scope into IAM mutation.** Runtime service-account role verification remains a separate follow-up because inherited/project-level IAM requires more careful read-only evaluation than a simple secret metadata check.

### Current blockers / unknowns

- The expanded `runtime/tests/test_gcp_deploy_doctor.py` needs empirical execution on an executable checkout.
- The doctor still checks Secret Manager resource existence, not whether the Cloud Run runtime service account has effective `secretAccessor` permission through project- or secret-level IAM.
- Gemini/Vertex AI production acceptance still requires a real authorized Google Cloud project and model access.
- The historical broader test-suite failures/errors still need systematic triage.

## Single best next step

**Add a read-only effective-permission check for the Cloud Run runtime service account against the four mounted Secret Manager secrets (covering project-level and secret-level `roles/secretmanager.secretAccessor` grants without reading secret payloads), with mocked regression tests before allowing `ready_to_deploy=true`.**

## Previous run — 2026-09-09 — Google Cloud deployment preflight

### Inspected at start

Read `progress.md` completely, inspected the current deployment helper `scripts/deploy_cloud_run.sh`, the onboarding doctor, and the current README/productization state. The prior next step called for broader failure triage, but the repository now has a proven live Docker/Grafana/MCP rehearsal and the larger remaining product risk is production deployment configuration. I therefore took a bounded deployment-reliability slice rather than reopening architecture.

### Official documentation checked

Verified the current Google Cloud guidance for:

- direct Cloud Run IAP using `gcloud run deploy ... --no-allow-unauthenticated --iap` plus the IAP service-agent `roles/run.invoker` binding;
- Secret Manager file mounts for Cloud Run;
- Cloud Run health-check/readiness behavior.

References used:

- https://cloud.google.com/run/docs/securing/identity-aware-proxy-cloud-run
- https://cloud.google.com/run/docs/configuring/services/secrets
- https://cloud.google.com/run/docs/configuring/instances/healthchecks

The existing deployment helper remains aligned with the current direct-IAP flow and secret-file mounting model.

### Exact changes made

Added `scripts/gcp_deploy_doctor.py`, a non-mutating Google Cloud pre-deployment checker. It validates:

- all environment variables consumed by `scripts/deploy_cloud_run.sh`;
- numeric `PROJECT_NUMBER` syntax;
- absolute Grafana URL syntax;
- Cloud Run runtime service-account email syntax;
- advisory Artifact Registry image-reference shape;
- local availability of `gcloud`;
- presence of an active gcloud identity without printing access tokens;
- target project accessibility and `PROJECT_ID`/`PROJECT_NUMBER` consistency;
- required Cloud Run, IAP, Secret Manager, and Cloud Logging APIs;
- existence/accessibility of the runtime service account;
- existence/accessibility of all four configured Secret Manager secrets without reading payloads;
- existence/accessibility of the configured Artifact Registry container image.

The doctor never enables APIs, reads secret values, changes IAM, deploys services, or mutates Google Cloud resources. It supports `--json` for automation and `--offline` for credential-free environment syntax validation.

During review, corrected an important readiness semantic: `--offline` can report `offline_checks_passed=true`, but it can never report `ready_to_deploy=true`. A successful offline run explicitly instructs the operator to rerun the live doctor before deployment.

Added `runtime/tests/test_gcp_deploy_doctor.py` with credential-free subprocess coverage for:

- valid offline deployment configuration;
- missing required variables;
- malformed project number;
- malformed Grafana URL;
- invalid runtime service-account identity;
- advisory-only handling of a non-Artifact-Registry-looking image reference;
- the invariant that offline checks never authorize deployment.

### Tests / checks / results

- Source-level review completed for the new doctor and tests.
- This automation environment exposes repository file APIs but not an executable repository checkout, so the new test module could not be executed here. No PASS claim is made for the new tests.
- No GitHub Actions workflow was added or triggered.
- No Google Cloud project, Grafana instance, Gemini endpoint, IAM binding, secret payload, or remediation endpoint was changed.

### Decisions made

1. **Deployment validation must be read-only.** The doctor reports missing APIs/resources rather than silently enabling or creating them.
2. **Offline syntax validation is not deployment authorization.** Live project/API/secret/image checks are mandatory before `ready_to_deploy` becomes true.
3. **Secret existence may be checked, secret contents may not.** The tool uses `gcloud secrets describe` only.
4. **Preserve the existing IAP boundary.** The standard Cloud Run artifact remains non-public and cannot enable remediation by environment flag.
5. **Avoid noisy CI.** The new regression suite is local/credential-free and no workflow was introduced.

### Current blockers / unknowns

- `runtime/tests/test_gcp_deploy_doctor.py` still needs empirical execution on a real checkout.
- Live Google Cloud deployment acceptance still requires an authorized project, service account, four Secret Manager secrets, an Artifact Registry image, and IAP configuration.
- Gemini/Vertex AI production acceptance still requires real Google Cloud credentials and enabled model access.
- The historically observed broader test-suite failures/errors still need systematic triage after deployment-path validation.

## Validation baseline retained

- Local onboarding doctor: 8 tests passed, 1 expected platform-specific permission test skipped on Windows.
- Focused judge/core/API/UI suite from the last executable run: 81/81 passed.
- Historical full suite baseline: 352 tests, 9 failures, 15 errors, 19 skipped; no full-suite green claim.
- Live Docker rehearsal: PASS twice consecutively.
- Official Grafana MCP read-only smoke path: PASS using `grafana/mcp-grafana:1.3.0`.
- Incident flow: investigate → diagnose `uplink-b packet loss` → exact revision approval → bounded remediation → telemetry-verified recovered.
- Gemini: integration implemented but not exercised in the last local capture because credentials were unavailable.

## Recent productization milestones

### Production onboarding doctor

`scripts/stageguard_doctor.py` validates Python 3.11+, strict telemetry mapping, `GRAFANA_URL`, token-file presence/non-emptiness/permissions without reading token contents, Grafana MCP launcher discovery, and optional activation-file presence. `runtime/preflight.py` remains authoritative for live Grafana/MCP evidence acceptance.

### Judge-facing/product presentation

The operator cockpit surfaces incident state, root cause, confidence, evidence revision, human approval, Grafana MCP provenance, and the `ACTION ACCEPTED ≠ INCIDENT RESOLVED` recovery-verification sequence. Bounded lifecycle responses expose provider, read-only status, datasource UID, query/recovery counts, and tool latency while excluding raw queries and secrets.

### Cross-platform persistence

Windows checkpoint/retention persistence was corrected to avoid unavailable `os.fchmod`, invalid fsync behavior on read-only handles, and unsupported directory-fsync assumptions.

### Release rehearsal telemetry gating

`scripts/demo_release.py` uses actual Prometheus healthy/fault evidence gates rather than timing sleeps, recreates the deterministic stack between takes, proves the official Grafana MCP smoke path, and only signals incident readiness when the telemetry StageGuard consumes is queryable.

### Live rehearsal

A Windows Docker Desktop Linux-engine rehearsal passed healthy evidence gates, official Grafana MCP smoke validation, real fault gates, diagnosis, exact revision approval, bounded recovery, and post-action telemetry verification twice consecutively. Grafana Explore showed the packet-loss fault plateau returning to baseline.

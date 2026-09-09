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

## Run log — 2026-09-09 — effective Secret Manager deployment authorization

### Inspected at start

Read `progress.md` completely, then inspected `scripts/gcp_deploy_doctor.py` and `runtime/tests/test_gcp_deploy_doctor.py`. The highest-value remaining deployment defect was exactly the previous handoff: the doctor verified that each Secret Manager resource existed, but did not prove that the Cloud Run runtime service account could actually read the mounted secret versions. A deployment could therefore pass preflight and fail at container startup because IAM was incomplete.

### Official documentation checked

Current Google Cloud documentation confirms:

- the underlying permission required to access a Secret Manager payload is `secretmanager.versions.access`, normally supplied by `roles/secretmanager.secretAccessor`;
- IAM Policy Troubleshooter checks a principal + full resource name + permission and explains effective access, including inherited allow/deny policy, without accessing the target data;
- the gcloud command is `gcloud policy-intelligence troubleshoot-policy iam RESOURCE --principal-email=... --permission=...`.

References:

- https://cloud.google.com/secret-manager/docs/access-secret-version
- https://cloud.google.com/iam/docs/roles-permissions/secretmanager
- https://cloud.google.com/policy-intelligence/docs/troubleshoot-access

### Exact changes made

Updated `scripts/gcp_deploy_doctor.py`:

- added `policytroubleshooter.googleapis.com` to the required production-preflight APIs;
- centralized the four mounted secret environment names;
- added a read-only `_secret_access_check()` for `secretmanager.versions.access`;
- uses IAM Policy Troubleshooter against each existing mounted secret and the configured runtime service account;
- checks the effective permission rather than assuming one particular predefined role, so custom/inherited grants can still succeed;
- treats `CAN_ACCESS` as success and `CANNOT_ACCESS`, unknown state, malformed JSON, or command failure as fail-closed deployment blockers;
- never invokes `gcloud secrets versions access` and never reads or prints secret payloads;
- only runs the permission proof after the secret metadata check succeeds;
- adds targeted remediation guidance for missing runtime secret access;
- keeps all checks non-mutating.

Updated `runtime/tests/test_gcp_deploy_doctor.py`:

- verifies Policy Troubleshooter is a required preflight API;
- adds credential-free unit coverage for `CAN_ACCESS`;
- adds fail-closed coverage for denied, unknown, malformed, and command-failure results;
- verifies the command checks `secretmanager.versions.access` against the Secret Manager full resource name;
- verifies the access check never invokes a secret-version read command;
- verifies next-step guidance names both the permission and the usual least-privilege `roles/secretmanager.secretAccessor` role.

Commits created this run:

- `f97be6537a09dc9e1e3dc90ab22a24f97101f83f` — effective Secret Manager runtime access verification
- `9411f6a6f36dd484dcd2f359f276d4badf9ebed4` — credential-free permission-check regression coverage

### Tests / checks / results

- Source-level review completed for the doctor/test changes and checked against current official Google Cloud IAM/Secret Manager documentation.
- This tool runtime does not expose an executable checkout of the connected GitHub repository. A direct public raw-file download attempt was also unavailable from the execution sandbox, so the updated unittest module could not be empirically run here.
- No PASS claim is made for the newly added tests in this run.
- No GitHub Actions workflow was added or triggered.
- No Google Cloud project, IAM policy, API, secret payload, Grafana instance, Gemini endpoint, or remediation endpoint was modified.

### Decisions made

1. **Verify the permission, not merely the role name.** `secretmanager.versions.access` is the runtime capability StageGuard needs; predefined, custom, and inherited IAM can all grant it.
2. **Use Policy Troubleshooter instead of reading a secret to test access.** Production preflight must never disclose payloads merely to prove deployment readiness.
3. **Fail closed on indeterminate IAM.** Unknown/failed troubleshooting cannot authorize deployment.
4. **Policy Troubleshooter is now a preflight dependency, not a runtime dependency.** The StageGuard Cloud Run service does not need that API to handle incidents after deployment.
5. **Do not mutate IAM automatically.** The doctor explains the missing grant but does not add it.

### Current blockers / unknowns

- `runtime/tests/test_gcp_deploy_doctor.py` needs empirical execution on an executable checkout.
- A real Google Cloud acceptance run is needed to confirm the exact Policy Troubleshooter resource-name behavior and operator permissions in a non-production project.
- Gemini/Vertex AI production acceptance still requires a real authorized Google Cloud project and model access.
- Historical broader-suite failures/errors still need systematic triage.

## Single best next step

**Run the complete Google Cloud deployment doctor against a disposable/non-production StageGuard project, capture the first real Policy Troubleshooter output for all four secrets, and then add a production acceptance test/fixture that locks the observed response contract before attempting the first Cloud Run deployment.**

## Validation baseline retained

- Local onboarding doctor: 8 tests passed, 1 expected platform-specific permission test skipped on Windows.
- Focused core/API/UI suite from the last executable run: 81/81 passed.
- Historical full suite baseline: 352 tests, 9 failures, 15 errors, 19 skipped; no full-suite green claim.
- Live Docker rehearsal: PASS twice consecutively.
- Official Grafana MCP read-only smoke path: PASS using `grafana/mcp-grafana:1.3.0`.
- Incident flow: investigate → diagnose `uplink-b packet loss` → exact revision approval → bounded remediation → telemetry-verified recovered.
- Gemini: integration implemented but not exercised in the last local capture because credentials were unavailable.

## Recent productization milestones

### Google Cloud deployment doctor

`scripts/gcp_deploy_doctor.py` validates deployment environment syntax, active gcloud identity, project-number consistency, required APIs, runtime service-account existence, mounted Secret Manager resources, effective runtime secret-version permission, and Artifact Registry image availability. `ENABLE_GEMINI=true` dynamically requires Vertex AI. Offline syntax checks never authorize deployment.

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

# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the read-only runtime evidence plane. The implemented vertical slice includes deterministic telemetry, Prometheus/Loki/Grafana, official Grafana MCP access, bounded investigation and diagnosis, optional Gemini briefing, exact-revision approval, remediation adapters, telemetry-verified recovery, authenticated lifecycle state, checkpoint/audit integrity, operator UI, Cloud Run deployment hardening, watchdog observability, authenticated private metrics bridging, evidence-unavailable abstention, no-replay execution reconciliation, recovery-only Grafana rechecks, stdio-only Grafana MCP launchers, strict operator-API authentication/framing/protocol preflight, and a loopback reference remediation provider with idempotent writes plus read-only operation reconciliation.

## Core invariants

- Grafana/MCP is read-only evidence access; infrastructure-write credentials remain isolated.
- Gemini is advisory and cannot mutate diagnosis, approval, remediation, or recovery state.
- Required evidence unavailability prevents briefing, approval, and execution from becoming actionable.
- Approval is exact-revision-bound and single-use; provider acceptance never counts as recovery.
- Fresh Grafana telemetry is required to verify recovery; `recovery_unverified` cannot replay remediation.
- Ambiguous remediation execution remains behind the execution-uncertainty barrier until durable reconciliation and fresh evidence resolve it.
- Operator API and reference remediation provider reject ambiguous credential/body framing before mutation.
- Consolidated validation resolves only direct non-symlink files under `runtime/tests`, fails closed on empty gates, is non-interactive and timeout-bounded, scrubs live credentials/proxies/Python injection controls, isolates Google ADC/gcloud homes and metadata identity, validates durable state, evidence/diagnosis, operator readiness/UI, remediation, deterministic Cloud Run deployment, cloud runtime metrics bridging, and runtime-observability contracts, executes overlapping selections once under their earliest owner, classifies subprocess launch failures as validation failures, and can audit/fail closed on safe runtime tests that are not owned by any production gate.

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected Windows-specific permission test skipped.
- Focused core/API/UI suite from the last executable repository run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating latest hardening/recovery work.
- Historical official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`; pinned `1.4.1` still requires a live smoke.
- Current connector-authored tests have not been repository-executed in this runner and are not treated as passing tests.

## Latest run — 2026-09-18 — deterministic Cloud Run deployment validation ownership

### Inspected at start

Read `progress.md` completely first, then inspected the repository tree, consolidated validator, Cloud Run deployment contract, Cloud Run entrypoint tests, and deploy-script subprocess test. The deployment tests are deterministic: contract tests inspect repository-local configuration; entrypoint tests construct argv from injected environment mappings; shell tests use a fake `gcloud` executable and temporary log rather than contacting Google Cloud.

### Changes / actions

- Added a `cloud deployment contract` production-validation gate owning exactly `test_cloud_run_deploy_contract.py`, `test_cloud_run_deploy_shell.py`, `test_deploy_cloud_run_script.py`, and `test_cloudrun_entrypoint.py`.
- Positioned deployment validation before the private metrics bridge and runtime observability, so production composition/configuration is validated before telemetry transport assumptions.
- Added `test_validation_cloud_deployment.py` to pin exact ownership and ordering and to ensure live Gemini/GCS/fake-cloud acceptance families cannot silently enter this gate.
- Kept credentialed deployment, live GCS, live Gemini, Docker, and fake-cloud restart acceptance outside this dependency-light gate.
- No credentials were read or supplied. No cloud resources, Docker, remediation targets, GitHub Actions, or unrelated repositories were touched.

### Checks / results

- Validator gate change committed as `b25c4aef6614d629af4f9e86560bf49f1cd7e952`.
- Deployment validation ownership contract committed as `45ab58c28b07fc496097848051e7b2be50b9daf4`.
- Repository inspection confirms the selected deployment tests use static inspection, injected environment data, or fake `gcloud`; they do not require live Google Cloud credentials.
- This connector environment still does not expose an executable checkout, so no new green-test claim is made and CI was intentionally not triggered as a substitute.

### Decisions

1. Treat deterministic Cloud Run composition and deploy-script safety as a production boundary because a correct application can still become unsafe through deployment wiring.
2. Use exact filenames instead of broad `test_cloud_run*.py` globs to prevent future credentialed acceptance tests from being selected automatically.
3. Keep the deployment gate before metrics/observability because identity, durable-state, secret-mount, and remediation-disablement wiring are prerequisites for trusting the deployed runtime.
4. Preserve the validator's credential-isolated subprocess environment even for tests that currently fake `gcloud`.

### Blockers / unknowns

- The consolidated runner still requires execution in a real checkout.
- Remaining unowned tests still need classification, especially retention, GCS/cloud-audit, fake-cloud restart, GCP deploy-doctor, simulator, and live Gemini acceptance families.
- Historical full-suite failures/errors still need classification from an executable checkout.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- Disposable private Cloud Run acceptance still requires suitable credentials/environment and Docker.

## Single best next step

Classify the retention family next: inspect planner/executor/coordinator/path-security tests and add a deterministic retention-safety gate if they are credential-free and non-destructive, while keeping any cloud deletion acceptance explicitly outside consolidated validation.

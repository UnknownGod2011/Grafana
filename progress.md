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
- Consolidated validation resolves only direct non-symlink files under `runtime/tests`, fails closed on empty gates, is non-interactive and timeout-bounded, scrubs live credentials/proxies/Python injection controls, isolates Google ADC/gcloud homes and metadata identity, validates durable state, retention safety, evidence/diagnosis, operator readiness/UI, remediation, deterministic Cloud Run deployment, cloud runtime metrics bridging, and runtime-observability contracts, executes overlapping selections once under their earliest owner, classifies subprocess launch failures as validation failures, and can audit/fail closed on safe runtime tests that are not owned by any production gate.

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected Windows-specific permission test skipped.
- Focused core/API/UI suite from the last executable repository run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating latest hardening/recovery work.
- Historical official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`; pinned `1.4.1` still requires a live smoke.
- Current connector-authored tests have not been repository-executed in this runner and are not treated as passing tests.

## Latest run — 2026-09-18 — retention safety validation ownership

### Inspected at start

Read `progress.md` completely first, then inspected the runtime test inventory, consolidated validator, retention executor tests, and retention coordinator CLI acceptance tests. The retention family is repository-local and deterministic: it uses temporary audit/checkpoint files, in-memory/fake telemetry and remediation, signed plans, subprocesses of the local coordinator, and simulated replace failures. No cloud deletion path is exercised.

### Changes / actions

- Added a `retention safety` production-validation gate owning exactly `test_retention_planner.py`, `test_retention_executor.py`, `test_retention_path_security.py`, and `test_retention_coordinator_cli.py`.
- Positioned retention immediately after durable-state integrity and before evidence/diagnosis because retention mutates audit storage whose checkpoint/anchor authority must already be validated.
- Added `test_validation_retention_safety.py` to pin exact ownership and ordering and prohibit broad wildcard/cloud/GCS admission into this gate.
- Kept any future cloud/GCS deletion acceptance outside this dependency-light gate by using exact filenames rather than `test_retention*.py`.
- No credentials were read or supplied. No cloud resources, Docker, live audit stores, remediation targets, GitHub Actions, or unrelated repositories were touched.

### Checks / results

- Retention gate committed as `9b544573b8b52104dd4b345b5794a8e9665ba4ce`.
- Retention validation ownership contract committed as `9e66f84e26e31f814f49bf0c0a417abc83e3704b`.
- Inspection confirms executor coverage includes signed-plan tamper rejection, checkpoint/audit drift refusal, backup preservation, owner-only backup intent, and failure-safe replacement; coordinator coverage includes prepare/execute subprocess behavior and restart/no-replay semantics.
- This connector environment still does not expose an executable checkout, so no new green-test claim is made and CI was intentionally not triggered as a substitute.

### Decisions

1. Treat retention as a production safety boundary because it is intentionally destructive to eligible historical audit records even though it preserves backups and anchored authority.
2. Require durable-state validation to precede retention so checkpoint/audit-anchor integrity is established before compaction behavior is trusted.
3. Use exact test filenames to prevent a future credentialed cloud-retention/deletion acceptance test from silently entering local production validation.
4. Preserve the existing isolated validation environment for retention subprocesses; the coordinator's test-only signing key is explicitly injected by its fixture rather than inherited from developer credentials.

### Blockers / unknowns

- The consolidated runner still requires execution in a real checkout.
- Remaining unowned tests still need classification, especially GCS/cloud-audit, fake-cloud restart, GCP deploy-doctor, simulator, and live Gemini acceptance families.
- Historical full-suite failures/errors still need classification from an executable checkout.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- Disposable private Cloud Run acceptance still requires suitable credentials/environment and Docker.

## Single best next step

Classify the GCP deploy-doctor family next: determine which doctor/identifier tests are deterministic with fake `gcloud`, add a credential-free deployment-readiness gate for those contracts, and keep any test capable of consulting real gcloud account/project state outside consolidated validation.

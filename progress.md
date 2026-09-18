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
- Cloud Logging audit filters treat incident/log identifiers as bounded literals and reject raw control characters before issuing queries.
- Consolidated validation resolves only direct non-symlink files under `runtime/tests`, fails closed on empty gates, is non-interactive and timeout-bounded, scrubs live credentials/proxies/Python injection controls, isolates Google ADC/gcloud homes and metadata identity, validates the deterministic telemetry simulator before evidence consumers, durable state, fake-cloud durability/restart behavior, fake execution/reconciliation CAS concurrency, retention safety, evidence/diagnosis, operator readiness/UI, remediation, deterministic Cloud Run deployment and GCP deployment readiness, cloud runtime metrics bridging, and runtime-observability contracts, executes overlapping selections once under their earliest owner, classifies subprocess launch failures as validation failures, and can audit/fail closed on safe runtime tests that are not owned by any production gate. Execution-safety, telemetry-simulator, and Cloud Run metrics-bridge ownership are exact-filename based so newly added tests cannot silently enter dependency-light validation.

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected Windows-specific permission test skipped.
- Focused core/API/UI suite from the last executable repository run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating latest hardening/recovery work.
- Historical official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`; pinned `1.4.1` still requires a live smoke.
- Current connector-authored tests have not been repository-executed in this runner and are not treated as passing tests.

## Latest run — 2026-09-18 — deterministic telemetry simulator validation ownership

### Inspected at start

Read `progress.md` completely first, then inspected the repository metadata, `runtime/tests` inventory, `runtime/tests/test_simulator.py`, and `scripts/run_stageguard_validation.py`. The simulator contract imports only the repository-local simulator module and exercises in-memory `SimulationState` fixtures; it does not require Docker, Grafana, Google Cloud, credentials, external networking, or remediation access.

### Changes / actions

- Added an exact-filename `telemetry simulator` gate owning only `test_simulator.py`.
- Positioned the gate immediately after runtime activation and before evidence/diagnosis consumers so deterministic source telemetry is validated before downstream interpretation contracts.
- Added `test_validation_telemetry_simulator.py` to pin exact ownership, prohibit wildcard selectors for this gate, enforce ordering before evidence consumers, and ensure `test_simulator.py` has exactly one owner.
- Kept live/credentialed acceptance outside dependency-light validation.
- No credentials, cloud resources, Docker, Grafana instances, remediation targets, GitHub Actions, or unrelated repositories were touched.

### Checks / results

- Manual contract inspection confirmed `test_simulator.py` is deterministic and dependency-light: it validates the fault fixture's four evidence classes, healthy packet-loss/fault state, and replayable reset behavior using only in-memory state.
- Validation runner update committed as `56c8a0fa229a29b35d26ffb8ab5aef59681cf186`.
- Ownership regression committed as `7a5589a15ede517ceed31eb9088af659691051d9`.
- The connector environment does not expose an executable checkout, so no new green-test claim is made and CI was intentionally not triggered as a substitute.

### Decisions

1. The telemetry generator is part of the production validation chain because downstream Grafana/evidence tests are only meaningful if the deterministic source fixture itself remains stable.
2. Use exact ownership for the simulator rather than a broad simulator wildcard; future simulator tests must be inspected before admission.
3. Keep the simulator gate before evidence consumers to make validation output reflect the data-flow dependency.

### Blockers / unknowns

- The consolidated runner still requires execution in a real checkout.
- Historical full-suite failures/errors still need classification from an executable checkout.
- Remaining unowned safe runtime tests need explicit classification before `--require-full-coverage` can be promoted as a release criterion.
- Live Gemini acceptance remains intentionally credentialed and should not be admitted to this dependency-light runner.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- Disposable private Cloud Run acceptance still requires suitable credentials/environment and Docker.

## Single best next step

Audit the remaining unowned safe runtime-test inventory and explicitly classify each dependency-light contract versus intentionally live/credentialed acceptance; then add a regression that pins the intentional exclusion set so `--require-full-coverage` can become a meaningful local release criterion without accidentally pulling live integrations into validation.

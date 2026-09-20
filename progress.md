# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the read-only runtime evidence plane. The implemented vertical slice includes deterministic telemetry, Prometheus/Loki/Grafana, official Grafana MCP access, bounded investigation and diagnosis, optional Gemini briefing, exact-revision approval, remediation adapters, telemetry-verified recovery, authenticated lifecycle state, checkpoint/audit integrity, operator UI, Cloud Run deployment hardening, watchdog observability, authenticated private metrics bridging, evidence-unavailable abstention, no-replay execution reconciliation, recovery-only Grafana rechecks, stdio-only Grafana MCP launchers, strict operator-API authentication/framing/protocol preflight, a loopback reference remediation provider with idempotent writes plus read-only operation reconciliation, and dedicated Grafana alert/dashboard surfaces for the authoritative composite lifecycle safety state.

## Core invariants

- Grafana/MCP is read-only evidence access; infrastructure-write credentials remain isolated.
- Gemini is advisory and cannot mutate diagnosis, approval, remediation, or recovery state.
- Required evidence unavailability prevents briefing, approval, and execution from becoming actionable.
- Approval is exact-revision-bound and single-use; provider acceptance never counts as recovery.
- Fresh Grafana telemetry is required to verify recovery; `recovery_unverified` cannot replay remediation.
- Ambiguous remediation execution remains behind the execution-uncertainty barrier until durable reconciliation and fresh evidence resolve it.
- Operator API and reference remediation provider reject ambiguous credential/body framing before mutation.
- Production remediation accepts only canonical operation IDs, bounded canonical target identities, frozen execution/reconciliation capabilities, exact validated transport/reconciliation result types, and bounded finite policy configuration.
- Consolidated validation is credential-isolated, timeout-bounded, non-interactive, and tracks safe runtime-test ownership explicitly.

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected Windows-specific permission test skipped.
- Focused core/API/UI suite from the last executable repository run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating latest hardening/recovery work.
- Historical official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`; pinned `1.4.1` still requires a live smoke.
- Connector-authored changes since the last executable checkout are not treated as passing tests.

## Recent completed work

- Added an unattended local acceptance path with `python scripts/demo_release.py --non-interactive`; it preserves stack recreation, Grafana MCP smoke, healthy evidence gates, deterministic fault injection, and post-fault evidence gates while removing only the human stdin pause. Regression coverage lives in `runtime/tests/test_validation_demo_release_noninteractive.py`.
- Closed inherited Git/environment isolation paths in the consolidated validator and retained explicit safe Git overrides.
- Added critical Grafana alert `stageguard-lifecycle-unsafe` from the authoritative fixed-cardinality `stageguard_lifecycle_safety_state` metric; missing data is alerting.
- Added a dedicated read-only `StageGuard Lifecycle Safety` Grafana dashboard for the authoritative one-hot lifecycle state, telemetry freshness, scrape transport, and separate recovery proof.
- Added `docs/runbooks/lifecycle-safety.md`, an operator procedure that preserves StageGuard's no-replay and telemetry-verified recovery invariants during lifecycle incidents.

## Latest run — 2026-09-20 — lifecycle safety operator runbook

### Inspected at start

Read `progress.md` completely before deciding what to change. Inspected the new lifecycle dashboard, its regression test, and the provisioned `stageguard-lifecycle-unsafe` alert. The observability surfaces now expose the lifecycle boundary, but operators did not have a repository-owned procedure for safely distinguishing evidence loss, checkpoint conflict, audit-integrity failure, execution uncertainty, and recovery verification. That is operationally risky because execution uncertainty must never be resolved by replaying a remediation write.

### Exact changes made

- Added `docs/runbooks/lifecycle-safety.md`.
- Defined a fail-closed first-response sequence: establish Grafana evidence availability, check freshness/transport, then identify the authoritative one-hot lifecycle state.
- Added state-specific procedures for checkpoint conflict, audit-integrity failure, execution uncertainty, and combined unsafe states.
- For execution uncertainty, explicitly requires read-only operation reconciliation using the canonical operation ID and forbids a second remediation write as a discovery mechanism.
- Kept provider acceptance separate from recovery and requires fresh Grafana telemetry plus StageGuard recovery verification before considering the incident recovered.
- Added concrete post-recovery gates for `stageguard_recovery_verified`, `stageguard_lifecycle_safety_state{state="ok"}`, `/readyz`, and the Grafana alert returning to Normal.
- Added evidence-retention guidance that explicitly excludes bearer tokens, provider credentials, API keys, and authorization headers.
- Added escalation criteria and the local consolidated-validation/unattended-rehearsal commands.
- Runbook commit: `69a363b921275599c060cc256007b48450ef86a1`.
- No credentials, live Grafana instance, remediation target, cloud resource, or GitHub Actions workflow was touched.

### Checks / results

- Static repository inspection and GitHub writes completed successfully.
- The runbook is consistent with the current dashboard queries and lifecycle alert semantics inspected in this run.
- This connector does not expose an executable checkout, so no test/Docker execution was possible and no new green-suite claim is made.

### Decisions

1. Execution uncertainty is an at-most-once safety problem: reconcile read-only before any subsequent write.
2. Evidence loss and unsafe lifecycle state are separate conditions; operators must restore trustworthy evidence before inferring recovery.
3. Provider acceptance is never a recovery signal; recovery remains telemetry-verified.
4. Incident notes must retain identifiers/evidence but never operational secrets.

### Blockers / unknowns

- This repository connector can inspect/update text but cannot execute the test suite or Docker stack.
- Historical full-suite failures/errors still need classification from an executable checkout.
- Live Gemini acceptance remains intentionally credentialed and outside the dependency-light runner.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.

## Single best next step

In the first executable Docker-capable checkout, run `python scripts/run_stageguard_validation.py --require-full-coverage --keep-going`; fix every concrete failure it exposes, then run `python scripts/demo_release.py --non-interactive` and verify the lifecycle alert/dashboard against the pinned Grafana MCP `1.4.1` stack. If those gates pass, the next product-level improvement should link the lifecycle alert/dashboard directly to the repository-owned runbook without introducing mutable Grafana controls.

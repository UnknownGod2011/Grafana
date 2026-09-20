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

## Latest run — 2026-09-20 — Grafana lifecycle safety alert

### Inspected at start

Read `progress.md` completely before deciding what to change. Inspected the runtime API's readiness/Prometheus safety model, Docker Compose stack, Grafana provisioning tree, and the existing watchdog alert group. Confirmed that StageGuard already exports a fixed-cardinality one-hot `stageguard_lifecycle_safety_state` metric covering checkpoint conflict, audit-integrity failure, execution uncertainty, and combined execution/audit failure, and that `/readyz` fails closed when lifecycle safety is not `ok`. The existing Grafana rules alert remediation deadline, stale telemetry, scrape failure, and recovery/checkpoint inconsistency, but did not alert the composite lifecycle safety invariant itself.

### Exact changes made

- Added `runtime/grafana/provisioning/alerting/stageguard-lifecycle-safety.yml`.
- Added critical Grafana alert `stageguard-lifecycle-unsafe`, driven by `max(stageguard_lifecycle_safety_state{state!="ok"})`.
- Configured `noDataState: Alerting` and `execErrState: Error` so the safety alert fails visibly when its evidence disappears or evaluation fails.
- Kept the alert read-only: it contains no approval, execution, provider, credential, or remediation action path. Its operator guidance explicitly forbids replaying remediation merely to clear the alert.
- Added `runtime/tests/test_validation_grafana_lifecycle_alert.py` to lock the composite query, fail-visible behavior, critical labeling, and absence of mutation/provider action strings. The filename is owned by the existing `test_validation_*.py` consolidated-validation gate.
- Alert implementation commit: `81a713fc82f98248ae07916a7e6df208ddc45c67`.
- Regression commit: `029c27acbef8458baaba429c47cc41b442aea7f1`.
- No credentials, live Grafana instance, remediation target, cloud resource, or GitHub Actions workflow was touched.

### Checks / results

- Static repository inspection and GitHub writes completed successfully.
- The connector does not expose an executable checkout, so the new regression and Grafana provisioning load were not executed; no green-suite claim is made.
- The alert consumes an already-exported fixed-cardinality metric rather than introducing a second safety-state implementation in Grafana.

### Decisions

1. Grafana should surface StageGuard's authoritative composite lifecycle invariant rather than independently recomputing checkpoint/audit/reconciliation logic.
2. A missing composite safety signal is operationally unsafe, so no-data is alerting rather than benign.
3. Grafana remains an indispensable observability/evidence layer, not a remediation execution plane.

### Blockers / unknowns

- This repository connector can inspect/update text but cannot execute the test suite or Docker stack.
- Historical full-suite failures/errors still need classification from an executable checkout.
- Live Gemini acceptance remains intentionally credentialed and outside the dependency-light runner.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.

## Single best next step

In the first executable Docker-capable checkout, run `python scripts/run_stageguard_validation.py --require-full-coverage --keep-going`; fix every concrete failure it exposes, then run `python scripts/demo_release.py --non-interactive` and verify in Grafana that `stageguard-lifecycle-unsafe` provisions cleanly and remains Normal while the lifecycle state is `ok`.

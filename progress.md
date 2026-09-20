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

## Latest run — 2026-09-20 — lifecycle safety operator dashboard

### Inspected at start

Read `progress.md` completely before deciding what to change. Inspected the lifecycle-safety alert, Grafana dashboard provisioning provider, and the existing `StageGuard Runtime Safety` dashboard. The alert now exposes the composite lifecycle invariant, but the operator dashboard still only visualized remediation watchdog/recovery metrics and did not show the authoritative lifecycle state or distinguish unsafe state from missing/stale lifecycle telemetry.

### Exact changes made

- Added `runtime/grafana/dashboards/stageguard-lifecycle.json`, provisioned automatically by the existing `/var/lib/grafana/dashboards` provider.
- Added a fail-visible lifecycle safety stat driven by `max(stageguard_lifecycle_safety_state{state!="ok"})` rather than duplicating application safety logic.
- Added a complete one-hot lifecycle-state timeline (`stageguard_lifecycle_safety_state`, legend by `state`) so operators can distinguish checkpoint conflict, audit-integrity failure, execution uncertainty, and combined states from a generic unsafe flag.
- Added lifecycle telemetry freshness using `timestamp(...)` plus `absent(...)`; missing lifecycle evidence renders as a very large age rather than healthy.
- Added runtime scrape transport health and recovery proof panels to separate evidence availability and recovery verification from the lifecycle invariant.
- Kept the dashboard non-editable/read-only and free of approval, execution, provider-token, or HTTP mutation controls.
- Added `runtime/tests/test_validation_grafana_lifecycle_dashboard.py` to lock dashboard identity/provisionability assumptions, authoritative metric queries, fail-visible freshness semantics, separate recovery proof, and absence of mutation surfaces.
- Dashboard commit: `c41d2e5881551e42615f462e99c553dbfdb4a8ed`.
- Regression commit: `2e7dca02e74c9ce561d5b1bee9ce9cd07dc0dc60`.
- No credentials, live Grafana instance, remediation target, cloud resource, or GitHub Actions workflow was touched.

### Checks / results

- Static repository inspection and GitHub writes completed successfully.
- The dashboard JSON was authored as a Grafana schema-v39 provisioned dashboard using the repository's existing `stageguard-prometheus` datasource UID and existing dashboard provider.
- This connector does not expose an executable checkout, so the new regression and live Grafana provisioning were not executed; no green-suite claim is made.

### Decisions

1. Operators need both the composite unsafe flag and the underlying one-hot state; Grafana should display both but never recompute the lifecycle state machine.
2. Missing lifecycle telemetry must be visible as evidence loss, not silently interpreted as safe.
3. Recovery verification remains a separate proof obligation from lifecycle safety and is shown separately.
4. Grafana remains an indispensable read-only observability/evidence layer; the dashboard intentionally contains no remediation controls.

### Blockers / unknowns

- This repository connector can inspect/update text but cannot execute the test suite or Docker stack.
- Historical full-suite failures/errors still need classification from an executable checkout.
- Live Gemini acceptance remains intentionally credentialed and outside the dependency-light runner.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.

## Single best next step

In the first executable Docker-capable checkout, run `python scripts/run_stageguard_validation.py --require-full-coverage --keep-going`; fix every concrete failure it exposes, then run `python scripts/demo_release.py --non-interactive` and verify that both `stageguard-lifecycle-unsafe` and the new `StageGuard Lifecycle Safety` dashboard provision cleanly, show fresh evidence, and remain safe/Normal while the runtime lifecycle state is `ok`.

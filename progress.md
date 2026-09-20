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
- Linked the lifecycle dashboard directly to that repository-owned operator runbook and added validation-owned regression coverage so the operational path cannot silently disappear or become a mutable control surface.

## Latest run — 2026-09-20 — lifecycle dashboard → runbook integration

### Inspected at start

Read `progress.md` completely before deciding what to change. Inspected the repository tree, `runtime/grafana/dashboards/stageguard-lifecycle.json`, and the existing lifecycle-safety runbook. The previous run correctly identified the next product-level gap: Grafana exposed the authoritative safety state but did not provide an operator-direct path to the safe response procedure.

### Exact changes made

- Updated `runtime/grafana/dashboards/stageguard-lifecycle.json` with a dashboard-level `Lifecycle safety runbook` link to `docs/runbooks/lifecycle-safety.md` on the canonical repository branch.
- The link opens separately, preserves dashboard time context, passes no dashboard variables, and contains no credential or mutation parameters.
- Bumped the provisioned dashboard version from 1 to 2.
- Added `runtime/tests/test_validation_lifecycle_dashboard_runbook.py`.
- Regression coverage verifies the repository-owned runbook exists, exactly one dashboard link targets it, the dashboard remains non-editable, lifecycle/recovery evidence remains present, and obvious approval/execution/credential markers are absent.
- Dashboard commit: `d20f61ca7ef1fcab72768ee5321ef2cde601ff17`.
- Regression-test commit: `dfd56e2af40c7f981f2702a5d167e844161b45f2`.
- No credentials, live Grafana instance, remediation target, Docker/cloud resource, or GitHub Actions workflow was touched.

### Checks / results

- JSON/dashboard structure was inspected before update and GitHub accepted the updated UTF-8 JSON file.
- Static regression coverage was added under the validation-owned `test_validation_*.py` convention.
- This connector does not expose an executable checkout, so the new test, Grafana provisioning, consolidated validation, and Docker rehearsal were not executed. No new green-suite claim is made.

### Decisions

1. Lifecycle observability should lead directly to the safe operator procedure, but Grafana remains a read-only evidence/navigation plane.
2. The dashboard link deliberately targets repository documentation rather than an API action, webhook, or remediation endpoint.
3. Runbook-link presence and absence of obvious mutable controls are now repository invariants guarded by a validation test.
4. Dashboard time context is retained for operator continuity; variables are not propagated to the external documentation URL.

### Blockers / unknowns

- This repository connector can inspect/update text but cannot execute the test suite or Docker stack.
- Historical full-suite failures/errors still need classification from an executable checkout.
- Live Gemini acceptance remains intentionally credentialed and outside the dependency-light runner.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.

## Single best next step

In the first executable Docker-capable checkout, run `python scripts/run_stageguard_validation.py --require-full-coverage --keep-going`; fix every concrete failure it exposes, then run `python scripts/demo_release.py --non-interactive`. Verify that Grafana provisions the lifecycle dashboard version 2 and its runbook link, that `stageguard-lifecycle-unsafe` remains Normal while lifecycle state is `ok`, and that the pinned `grafana/mcp-grafana:1.4.1` read-only smoke succeeds. After those gates pass, prioritize failures revealed by real execution over additional speculative hardening.

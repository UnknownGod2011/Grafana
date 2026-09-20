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

- Added an unattended local acceptance path with `python scripts/demo_release.py --non-interactive`; it preserves stack recreation, Grafana MCP smoke, healthy evidence gates, deterministic fault injection, and post-fault evidence gates while removing only the human stdin pause.
- Added opt-in `--cleanup` to the release rehearsal so unattended runs can deterministically tear down the compose stack on success, evidence failure, or partial startup failure without touching a pre-existing StageGuard API/stack.
- Closed inherited Git/environment isolation paths in the consolidated validator and retained explicit safe Git overrides.
- Added critical Grafana alert `stageguard-lifecycle-unsafe` from the authoritative fixed-cardinality `stageguard_lifecycle_safety_state` metric; missing data is alerting.
- Added a dedicated read-only `StageGuard Lifecycle Safety` Grafana dashboard for the authoritative one-hot lifecycle state, telemetry freshness, scrape transport, and separate recovery proof.
- Added `docs/runbooks/lifecycle-safety.md`, an operator procedure that preserves StageGuard's no-replay and telemetry-verified recovery invariants during lifecycle incidents.
- Linked the lifecycle dashboard directly to that repository-owned operator runbook and added validation-owned regression coverage so the operational path cannot silently disappear or become a mutable control surface.

## Latest run — 2026-09-20 — cleanup-safe unattended acceptance

### Inspected at start

Read `progress.md` completely before deciding what to change. Inspected `scripts/demo_release.py` and its validation-owned non-interactive regression tests. The unattended acceptance path could create/recreate local Docker resources but had no opt-in lifecycle cleanup, leaving containers running after success or a post-start failure.

### Exact changes made

- Refactored compose teardown into `_compose_down()` and retained `_recreate_compose_stack()` as the stale-telemetry reset boundary.
- Added `python scripts/demo_release.py --non-interactive --cleanup` for unattended/local acceptance runs that should leave no StageGuard compose resources behind.
- Cleanup executes in `finally`, so it runs after success, evidence-gate failure, and partial `demo_local.up()` failure.
- Ownership is established only after the pre-existing-API guard and stack recreation; therefore `--cleanup` refuses to tear down a pre-existing StageGuard API/stack it did not create.
- Extended `runtime/tests/test_validation_demo_release_noninteractive.py` with success cleanup, evidence-failure cleanup, partial-startup cleanup, and pre-existing-stack non-destruction cases.
- Implementation commits: `fd93efba052ef43fb1db1f699a63b4a0a4757915`, `417439fc7dce46ca3e6289727021e4ebf54c2eea`.
- Regression-test commits: `fd7820871e94eaa893a1b9e34aeccbb7026297c7`, `d93432308c3e92ad3d456b9209eac5f85323e78c`.
- No credentials, live Grafana instance, remediation target, cloud resource, or GitHub Actions workflow was touched.

### Checks / results

- GitHub accepted the Python source and regression-test updates.
- Static review confirms cleanup is opt-in and cannot run when the initial pre-existing StageGuard API guard fires.
- This repository connector does not expose an executable checkout, so the updated tests and Docker rehearsal were not executed. No new green-suite claim is made.

### Decisions

1. Cleanup remains opt-in so interactive/demo users can keep the local stack alive for investigation after the evidence gate succeeds.
2. Unattended acceptance should use `--cleanup` to avoid leaked local resources, especially after failed gates.
3. A partial startup is considered owned after the rehearsal has first cleared the local compose stack; this permits cleanup of containers created before `demo_local.up()` raises.
4. A pre-existing running StageGuard API remains a hard stop and is never cleaned up by this script.

### Blockers / unknowns

- This repository connector can inspect/update text but cannot execute the test suite or Docker stack.
- Historical full-suite failures/errors still need classification from an executable checkout.
- Live Gemini acceptance remains intentionally credentialed and outside the dependency-light runner.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.

## Single best next step

In the first executable Docker-capable checkout, run `python scripts/run_stageguard_validation.py --require-full-coverage --keep-going`; fix every concrete failure it exposes, then run `python scripts/demo_release.py --non-interactive --cleanup`. Verify Grafana provisions the lifecycle dashboard version 2 and its runbook link, `stageguard-lifecycle-unsafe` remains Normal while lifecycle state is `ok`, pinned `grafana/mcp-grafana:1.4.1` passes the read-only smoke, and the compose stack is absent after both successful and deliberately failed acceptance runs. After those gates pass, prioritize failures revealed by real execution over additional speculative hardening.

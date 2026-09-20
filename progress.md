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
- Local acceptance never destroys pre-existing compose resources merely because the StageGuard API is unreachable.
- Unattended cleanup must independently attempt all runtime components it owns, verify the host API is unreachable and compose has zero containers, and report any partial teardown as failure.
- API startup failure may terminate/reap only the exact `Popen` child created by that startup attempt; it must clear ownership metadata before returning failure.

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected Windows-specific permission test skipped.
- Focused core/API/UI suite from the last executable repository run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating latest hardening/recovery work.
- Historical official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`; pinned `1.4.1` still requires a live smoke.
- Connector-authored changes since the last executable checkout are not treated as passing tests.

## Recent completed work

- Added unattended local acceptance with `python scripts/demo_release.py --non-interactive` and opt-in `--cleanup`.
- Made compose teardown fail closed on non-zero exit and timeout-bounded at 45 seconds.
- Added a bounded compose ownership preflight so stopped, unhealthy, or partially-started pre-existing StageGuard containers are not destroyed when the API is unreachable.
- Fixed `--cleanup` to independently attempt host-API and compose cleanup, verify both postconditions, and aggregate failures rather than stranding one owned component when the other cleanup leg fails.
- Closed inherited Git/environment isolation paths in the consolidated validator and retained explicit safe Git overrides.
- Added critical Grafana alert `stageguard-lifecycle-unsafe`, a dedicated read-only lifecycle dashboard, and `docs/runbooks/lifecycle-safety.md` linked from that dashboard.
- Hardened local API startup ownership so early child exit and readiness timeout cannot leave stale PID metadata; timeout cleanup targets only the exact spawned child and escalates terminate -> bounded wait -> kill/reap.
- Hardened the final owned-child reap edge: kill is attempted only after a bounded terminate wait, a second bounded wait is mandatory, and a child that survives both produces an explicit `DemoError` while stale PID ownership metadata is still cleared.

## Latest run — 2026-09-21 — bound terminate/kill/reap failure semantics

### Inspected at start

Read `progress.md` completely before deciding what to change. Re-inspected `scripts/demo_local.py`, `runtime/tests/test_demo_local_spawn_lifecycle.py`, and the repository tree. The prior startup cleanup correctly targeted only its exact `Popen` child, but its second `wait(timeout=5)` after `kill()` could itself time out and leak a raw `subprocess.TimeoutExpired` outside the demo error contract. The kill-escalation branch also lacked focused regression coverage.

### Exact changes made

- Hardened `_reap_spawn_failure(process)` in `scripts/demo_local.py` so terminate and kill remain separately bounded to five seconds.
- Added race-safe handling for `ProcessLookupError` when the exact owned child exits between `poll()` and terminate/kill.
- If the exact child still cannot be reaped after terminate and kill, cleanup now raises an explicit `DemoError` rather than leaking a raw subprocess exception or implying cleanup succeeded.
- Kept PID metadata cleanup in `finally`, including the unreapable-child path, so stale ownership metadata is never retained.
- Added regressions proving kill escalation occurs only after terminate wait timeout and proving the unreapable-child path fails closed while clearing PID state.
- Implementation commit: `53ab344f062a1b0b93449a4aa2d2aa59182b3d49`.
- Regression commit: `38a4bdcc569db74f440d55a0ae0b13e71ef5db51`.
- No credentials, live Grafana instance, remediation target, cloud resource, unrelated repository, or GitHub Actions workflow was touched.

### Checks / results

- GitHub accepted both source and regression updates.
- Static review confirms the cleanup authority remains the exact `Popen` object and no host PID discovery or port killing was introduced.
- This repository connector does not expose an executable checkout, so the new regressions, consolidated validator, Docker rehearsal, and live MCP smoke were not executed; no new green-suite claim is made.

### Decisions

1. An owned child surviving both terminate and kill is an explicit cleanup failure, not a successful startup failure cleanup.
2. PID metadata is removed even when the OS refuses to reap the child, because the PID file must not falsely claim safe/manageable ownership after cleanup authority has failed.
3. Process-exit races are benign only when they concern the exact child already owned by the current invocation.
4. Preserve the existing no-port-killing/no-arbitrary-PID-discovery safety boundary.

### Blockers / unknowns

- The connector can update repository files but cannot execute the checkout, so focused pytest and consolidated validation remain unexecuted here.
- Historical full-suite failures/errors still need classification from an executable checkout.
- Live Gemini acceptance remains intentionally credentialed and outside the dependency-light runner.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.

## Single best next step

Run `runtime/tests/test_demo_local_spawn_lifecycle.py` in an executable checkout first. If green, run the consolidated validator and `python scripts/demo_release.py --non-interactive --cleanup`; then run the pinned `grafana/mcp-grafana:1.4.1` read-only smoke and prioritize any failures revealed by real execution.

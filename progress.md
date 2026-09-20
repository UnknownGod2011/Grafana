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

## Latest run — 2026-09-21 — implement failed API-spawn ownership cleanup

### Inspected at start

Read `progress.md` completely before deciding what to change. Re-inspected `scripts/demo_local.py` and the focused `runtime/tests/test_demo_local_spawn_lifecycle.py` regressions created in the previous run. Confirmed the implementation still left stale PID metadata on pre-health exit and left the exact spawned child alive on readiness timeout.

### Exact changes made

- Added `_reap_spawn_failure(process)` to `scripts/demo_local.py`.
- On pre-health child exit, startup now reaps the already-exited child where supported and always removes the ownership PID file before raising `DemoError`.
- On readiness timeout, startup now terminates only the exact `Popen` child created by the current call, waits up to 5 seconds, escalates to `kill()` only after `subprocess.TimeoutExpired`, performs a second bounded reap, and clears the PID file in a `finally` block.
- Kept the no-port-killing/no-host-PID-discovery boundary intact.
- Implementation commit: `cabf293c8abde04c65db349749ff8f61d05c80ef`.
- No credentials, live Grafana instance, remediation target, cloud resource, unrelated repository, or GitHub Actions workflow was touched.

### Checks / results

- GitHub accepted the implementation update.
- Static review matches the two focused regression expectations: early exit removes PID state; timeout calls `terminate()`, performs bounded `wait()`, and removes PID state.
- This repository connector still does not expose an executable checkout, so no pytest, Docker, or live MCP command was run and no new green-suite claim is made.

### Decisions

1. Cleanup authority comes from possession of the exact `Popen` object, not from a PID file or listening port.
2. PID metadata is ownership state and must be removed on every failed startup path.
3. Termination is bounded and escalates to kill only for the exact owned child after a timeout.
4. Preserve all production safety boundaries: no arbitrary host process discovery, no port killing, no infrastructure mutation through Grafana/MCP.

### Blockers / unknowns

- The connector can update repository files but cannot execute the checkout, so the focused regressions and consolidated validator remain unexecuted in this environment.
- Historical full-suite failures/errors still need classification from an executable checkout.
- Live Gemini acceptance remains intentionally credentialed and outside the dependency-light runner.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.

## Single best next step

Run `runtime/tests/test_demo_local_spawn_lifecycle.py` first in an executable checkout and fix any behavioral mismatch, then run the consolidated validator and `python scripts/demo_release.py --non-interactive --cleanup`. After those pass, run the pinned `grafana/mcp-grafana:1.4.1` read-only smoke and prioritize failures revealed by real execution.

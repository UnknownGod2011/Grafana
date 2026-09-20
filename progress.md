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

## Latest run — 2026-09-21 — specify failed API-spawn ownership cleanup

### Inspected at start

Read `progress.md` completely before deciding what to change. Inspected `scripts/demo_local.py`, especially `_spawn_api()` and `_stop_api()`, after the previous run identified startup PID handling as the next process-lifecycle edge case. Confirmed a concrete defect: `_spawn_api()` writes the newly created child PID before readiness, but if the child exits before health or remains alive without becoming healthy for 30 seconds, the function raises without clearing the PID file; in the timeout case it also leaves the exact child process it just created running.

### Exact changes made

- Added `runtime/tests/test_demo_local_spawn_lifecycle.py` as a focused regression specification for this ownership boundary.
- The first regression requires a child that exits before health to leave no stale ownership PID file.
- The second regression requires a startup timeout to terminate/reap only the exact `Popen` child created by `_spawn_api()` and then remove its PID file; it deliberately does not authorize host-wide PID discovery or port killing.
- Regression-spec commit: `83d5752fcbbaea22ffb4d3ccbb8dc9e69e1468da`.
- No credentials, live Grafana instance, remediation target, cloud resource, unrelated repository, or GitHub Actions workflow was touched.

### Checks / results

- GitHub accepted the focused regression specification.
- Static inspection shows these two regressions expose current behavior and are therefore expected to fail until `_spawn_api()` owns failure cleanup for its exact child. They are not recorded as green tests.
- This repository connector does not expose an executable checkout, so no pytest or Docker command was run and no new green-suite claim is made.

### Decisions

1. A process created by the current `_spawn_api()` call is safe to terminate/reap on that call's startup failure; an arbitrary PID discovered later is not.
2. Startup failure must clear ownership metadata so later cleanup cannot confuse a dead/reused PID with a StageGuard-owned child.
3. Keep the existing no-port-killing rule and do not broaden cleanup to unrelated host processes.
4. Record the regression before changing lifecycle semantics so the intended safety boundary is explicit and executable.

### Blockers / unknowns

- The connector can replace whole files but does not expose a patch operation or executable checkout. The `_spawn_api()` source fix is therefore deliberately not claimed complete in this run; the new regression currently documents a known red edge case.
- Historical full-suite failures/errors still need classification from an executable checkout.
- Live Gemini acceptance remains intentionally credentialed and outside the dependency-light runner.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.

## Single best next step

Implement the minimal `_spawn_api()` failure cleanup against its exact `Popen` object: on pre-health child exit, remove the PID file; on readiness timeout, terminate the spawned child, wait with a short bound, kill/reap it only if necessary, then remove the PID file. Run `runtime/tests/test_demo_local_spawn_lifecycle.py` first, then the consolidated validator and `python scripts/demo_release.py --non-interactive --cleanup`. After those pass, run the pinned `grafana/mcp-grafana:1.4.1` read-only smoke and prioritize failures revealed by real execution.

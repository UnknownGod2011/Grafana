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
- A persisted local API PID is never sufficient authority to signal a process: shutdown must verify the live command signature first and retain metadata on ambiguous or failed termination.

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
- Hardened cross-invocation API shutdown against PID reuse: a PID loaded from disk is signalled only after bounded command-line inspection proves the expected StageGuard `bootstrap.py --identity-mode local --port 9110` signature.

## Latest run — 2026-09-21 — persistent PID ownership verification

### Inspected at start

Read `progress.md` completely before deciding what to change. Inspected the repository tree, `scripts/demo_local.py`, and `runtime/tests/test_demo_local_spawn_lifecycle.py`. Startup-failure cleanup was already constrained to the exact `Popen` child, but normal `stop` still trusted a numeric PID persisted on disk. If that API had died and the OS reused its PID while another process happened to answer the StageGuard health port, `_stop_api()` could signal an unrelated process. It also unlinked PID metadata even when SIGTERM failed to stop the API, discarding the only local ownership clue.

### Exact changes made

- Added `_pid_command(pid)`, a two-second-bounded best-effort process command lookup using `/proc/<pid>/cmdline` where available, `ps` on other POSIX systems, and non-interactive PowerShell CIM lookup on Windows.
- Added `_pid_matches_stageguard_api(pid)` requiring the expected `bootstrap.py`, `--identity-mode local`, and `--port 9110` signature before persistent PID state grants signal authority.
- Changed `_stop_api()` to refuse signalling an unverified/reused PID rather than trusting the PID file plus health endpoint.
- Invalid PID metadata is now removed only when the API is unreachable; if the API is reachable, shutdown fails closed for manual inspection.
- Permission/OS failures while signalling a verified PID now surface as `DemoError` instead of being silently ignored.
- After SIGTERM, shutdown now requires the health endpoint to become unreachable within five seconds; otherwise it fails and deliberately retains PID metadata for safe follow-up.
- Added focused regressions for reused/unverified PID refusal, verified shutdown, failed-shutdown metadata retention, and strict command-signature matching.
- Implementation commit: `d564180357db930f1addc0813a983e5dba3eacdd`.
- Regression commit: `16338b373c5b98aa0ab5c7e49b349bb15741933e`.
- No credentials, live Grafana instance, remediation target, cloud resource, unrelated repository, or GitHub Actions workflow was touched.

### Checks / results

- GitHub accepted both source and regression updates.
- Static review confirms persisted PID state can no longer directly authorize `os.kill`; process identity must be independently inspected first.
- Identity lookup is timeout-bounded and fails safe when process metadata cannot be read.
- This repository connector does not expose an executable checkout, so the new regressions, consolidated validator, Docker rehearsal, and live MCP smoke were not executed; no new green-suite claim is made.

### Decisions

1. PID files are hints, not process-termination capabilities; PID reuse is expected OS behavior and must be defended against.
2. Failure to inspect a process command is a reason to refuse termination, never a reason to weaken ownership checks.
3. A failed verified shutdown retains PID metadata because deleting it would make subsequent operator recovery less safe.
4. No port-based process discovery or host-wide killing was introduced.

### Blockers / unknowns

- The connector can update repository files but cannot execute the checkout, so focused pytest and consolidated validation remain unexecuted here.
- The PowerShell CIM fallback requires live Windows validation; inability to inspect there fails safe rather than killing anything.
- Historical full-suite failures/errors still need classification from an executable checkout.
- Live Gemini acceptance remains intentionally credentialed and outside the dependency-light runner.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.

## Single best next step

Execute `runtime/tests/test_demo_local_spawn_lifecycle.py` on Linux and Windows (or at minimum Linux first), then run the consolidated validator and `python scripts/demo_release.py --non-interactive --cleanup`. If those pass, run the pinned `grafana/mcp-grafana:1.4.1` read-only smoke and prioritize any real execution failure over further lifecycle hardening.

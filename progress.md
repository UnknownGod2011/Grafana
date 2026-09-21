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
- A persisted local API PID is never sufficient authority to signal a process: shutdown must structurally verify the live command signature first and retain metadata on ambiguous or failed termination.
- Health reachability is not process ownership: a structurally verified unhealthy local API is still an owned process and must be cleaned up safely.
- Persisted PID metadata must be a strictly positive process ID before any lookup or signal; zero/negative POSIX PIDs can address process groups and are never valid StageGuard ownership handles.

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
- Added bounded compose ownership preflight so stopped, unhealthy, or partially-started pre-existing StageGuard containers are not destroyed when the API is unreachable.
- Fixed `--cleanup` to independently attempt host-API and compose cleanup, verify both postconditions, and aggregate failures rather than stranding one owned component when the other cleanup leg fails.
- Added critical Grafana lifecycle alert/dashboard/runbook surfaces.
- Hardened local API startup ownership so early child exit and readiness timeout cannot leave stale PID metadata; timeout cleanup targets only the exact spawned child and escalates terminate -> bounded wait -> kill/reap.
- Hardened cross-invocation API shutdown against PID reuse and replaced substring identity authorization with structured argv validation.
- Decoupled API health from process ownership during shutdown: verified unhealthy processes are now signalled, while unreachable/unverified stale PID metadata is discarded without signalling.
- Hardened persisted PID handling so zero and negative values can never reach process lookup or `os.kill`, preventing POSIX process-group signalling from corrupt metadata.

## Latest run — 2026-09-21 — special/nonpositive PID safety hardening

### Inspected at start

Read `progress.md` completely before deciding what to change. Inspected `scripts/demo_local.py` and `runtime/tests/test_demo_local_spawn_lifecycle.py`, focusing on termination authority and the persisted PID trust boundary.

### Finding

The PID-reuse work structurally verified command identity, but persisted PID parsing still accepted `0` and negative integers. On POSIX, `os.kill(0, sig)` targets the caller's process group and negative PIDs target process groups. Corrupt or malicious local PID metadata therefore had a dangerous semantic class that should be rejected before process lookup or structural matching.

### Exact changes made

- `_stop_api()` now rejects every nonpositive persisted PID before command lookup or signalling.
- If the API is reachable with nonpositive PID metadata, cleanup fails closed and retains the metadata for investigation.
- If the API is unreachable, nonpositive PID metadata is discarded as stale without signalling anything.
- `_pid_command()` and `_pid_matches_stageguard_api()` independently reject nonpositive/non-integer PID values as defense in depth.
- Added regressions for PID `0`, `-1`, and an arbitrary negative PID proving `os.kill` is never called, plus stale-unreachable cleanup and matcher short-circuit coverage.
- Implementation commit: `d2da2e4184b6bbb1d2360b8bc7ffd07629a09059`.
- Regression commit: `78f650d6eef9058f68a25b3151917d1a60036ce4`.
- No credentials, cloud resources, live remediation targets, unrelated repositories, or GitHub Actions workflows were touched.

### Checks / results

- GitHub accepted the implementation and regression updates.
- Static inspection establishes the new guard before `_pid_matches_stageguard_api()` and therefore before `os.kill()`.
- This connector does not expose an executable checkout, so no new green test claim is made. The focused lifecycle tests and broader validator remain execution gates.

### Decisions

1. Persisted PID files are untrusted local state; parsing as an integer is not sufficient validation.
2. Only strictly positive PIDs may enter StageGuard's cross-invocation ownership-verification path.
3. Reachable API + unsafe PID metadata remains ambiguous and fails closed; unreachable API + unsafe metadata can be discarded without any process action.
4. The invariant is enforced both at the shutdown boundary and lower-level PID identity helpers to reduce regression risk.

### Blockers / unknowns

- Focused lifecycle tests still require execution in a real checkout, including Windows command-line parsing validation.
- Historical full-suite failures/errors still need classification from an executable checkout.
- A live unattended Docker rehearsal is required after the accumulated cleanup hardening.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.

## Single best next step

Execute `runtime/tests/test_demo_local_spawn_lifecycle.py` on Linux and Windows, fix any platform-specific process-identity issues found, then run consolidated validation and `scripts/demo_release.py --non-interactive --cleanup`; after that, perform the pinned Grafana MCP `1.4.1` read-only smoke.

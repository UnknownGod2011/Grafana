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

## Latest run — 2026-09-21 — verified unhealthy API cleanup implementation

### Inspected at start

Read `progress.md` completely before deciding what to change. Inspected `scripts/demo_local.py` and `runtime/tests/test_demo_local_spawn_lifecycle.py`, focusing on the red regression from the previous run and the persisted-PID ownership/cleanup boundary.

### Finding

The red regression was valid: `_stop_api()` deleted PID metadata whenever `/healthz` was unavailable before attempting structural process identity verification. This could orphan an owned StageGuard API that was alive but unhealthy, hung, or still starting. Health status is service-state evidence, not process-ownership evidence.

### Exact changes made

- Changed `_stop_api()` to evaluate API reachability and structural PID identity independently.
- A structurally verified StageGuard local API is now sent SIGTERM even when `/healthz` is unavailable.
- An unverified PID is never signalled. If the API is also unreachable, stale PID metadata is safely discarded; if the API is reachable, cleanup fails closed and retains the metadata for manual investigation.
- After SIGTERM, shutdown now waits on structural process identity rather than health alone, so an unhealthy process must actually cease matching the owned command signature before cleanup is considered complete.
- `ProcessLookupError` is treated as an already-exited owned process and clears metadata; permission/OS signalling errors remain explicit failures.
- Updated lifecycle regressions so successful shutdown models ownership disappearing after SIGTERM, and added coverage for the unreachable + unverified stale-PID case.
- Implementation commit: `c4d8ece893db2b9b887312e3b8d98efeec1cc5a3`.
- Regression update commit: `40c6d8ea1353dd79e6e1700d2dce3c949b824248`.
- No credentials, cloud resources, live remediation targets, unrelated repositories, or GitHub Actions workflows were touched.

### Checks / results

- GitHub accepted both implementation and regression updates.
- Static inspection confirms the previous early-return-on-unhealthy path is removed and termination authority remains gated by `_pid_matches_stageguard_api()`.
- This connector does not expose an executable checkout, so no new green test claim is made. The focused lifecycle tests and broader validator remain execution gates.

### Decisions

1. Structural process identity, not HTTP health, is the authority for persisted-PID cleanup.
2. A reachable API plus unverified PID is ambiguous and must fail closed without signalling or discarding ownership metadata.
3. An unreachable API plus unverified PID is safe to classify as stale metadata because no termination action is taken.
4. Post-SIGTERM success is based on disappearance of the verified process identity, preventing a hung/unhealthy API from being mistaken for a successful stop merely because health is down.

### Blockers / unknowns

- Focused lifecycle tests still require execution in a real checkout, including Windows command-line parsing validation.
- Historical full-suite failures/errors still need classification from an executable checkout.
- A live unattended Docker rehearsal is required after the accumulated cleanup hardening.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.

## Single best next step

Execute `runtime/tests/test_demo_local_spawn_lifecycle.py` on Linux and Windows, fix any platform-specific process-identity issues found, then run consolidated validation and `scripts/demo_release.py --non-interactive --cleanup`; after that, perform the pinned Grafana MCP `1.4.1` read-only smoke.

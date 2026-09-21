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

## Latest run — 2026-09-21 — unhealthy owned API cleanup regression

### Inspected at start

Read `progress.md` completely before deciding what to change. Inspected `scripts/demo_local.py` and `runtime/tests/test_demo_local_spawn_lifecycle.py`, concentrating on the persisted-PID cleanup path after the prior structured identity hardening.

### Finding

`_stop_api()` currently deletes `stageguard-api.pid` immediately when `/healthz` is unreachable. That conflates service health with process ownership. A StageGuard API process can still be alive but hung, starting, or unhealthy; in that state cleanup discards its verified ownership handle without signalling it, potentially leaking the host process after an unattended acceptance run.

### Exact changes made

- Added `test_stop_api_terminates_verified_owned_process_even_when_health_is_down`.
- The regression requires `_stop_api()` to use the structural PID identity proof already implemented and send SIGTERM to that exact verified StageGuard process even when `/healthz` is down.
- The test simultaneously preserves the safety boundary: it grants termination authority only through `_pid_matches_stageguard_api`, never through port ownership or PID metadata alone.
- Regression commit: `675c6f954849e2c04504d88bb037c2fbb0ca7064`.
- No credentials, live Grafana instance, remediation target, cloud resource, unrelated repository, or GitHub Actions workflow was touched.

### Checks / results

- GitHub accepted the focused regression update.
- The new test is intentionally a red gate against the current `_stop_api()` implementation; current code returns early when health is down and therefore does not call `os.kill`.
- This connector does not expose an executable checkout, so no green test claim is made.

### Decisions

1. Health reachability is not process-ownership evidence and must not decide whether an owned process is cleaned up.
2. Structural command identity remains mandatory before signalling a persisted PID.
3. An unhealthy but structurally verified StageGuard process should be terminated during owned cleanup; an unverified PID must never be signalled.

### Blockers / unknowns

- The red regression requires the corresponding `_stop_api()` implementation change.
- Focused lifecycle tests still require execution in a real checkout, including Windows command-line parsing validation.
- Historical full-suite failures/errors still need classification from an executable checkout.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.

## Single best next step

Change `_stop_api()` so it structurally checks the persisted PID even when `/healthz` is unavailable: terminate only a verified StageGuard process, safely discard genuinely stale/unverified metadata when the API is also unreachable, retain metadata on ambiguous reachable-service ownership, and keep failure behavior fail-closed. Then execute the focused lifecycle suite before consolidated validation, unattended Docker cleanup rehearsal, and the pinned Grafana MCP `1.4.1` read-only smoke.

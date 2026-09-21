# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the read-only runtime evidence plane. The implemented vertical slice includes deterministic telemetry, Prometheus/Loki/Grafana, official Grafana MCP access, bounded investigation and diagnosis, optional Gemini briefing, exact-revision approval, remediation adapters, telemetry-verified recovery, authenticated lifecycle state, checkpoint/audit integrity, operator UI, Cloud Run deployment hardening, watchdog observability, authenticated private metrics bridging, evidence-unavailable abstention, no-replay execution reconciliation, recovery-only Grafana rechecks, stdio-only Grafana MCP launchers, strict operator-API authentication/framing/protocol preflight, a loopback reference remediation provider with idempotent writes plus read-only operation reconciliation, and Grafana lifecycle safety surfaces.

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
- Cleanup independently attempts all requested runtime components it owns and reports partial teardown as failure.
- API startup failure may terminate/reap only the exact `Popen` child created by that startup attempt.
- A persisted local API PID is never sufficient authority to signal a process; shutdown structurally verifies the live command signature first.
- Health reachability is not process ownership: a structurally verified unhealthy local API is still an owned process.
- Persisted PID metadata must be a strictly positive process ID before lookup or signal.
- Local stop must not report success if teardown of an owned component fails.

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected Windows-specific permission test skipped.
- Focused core/API/UI suite from the last executable repository run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating latest hardening/recovery work.
- Historical official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`; pinned `1.4.1` still requires a live smoke.
- Connector-authored changes since the last executable checkout are not treated as passing tests.

## Recent completed work

- Added unattended local acceptance with `python scripts/demo_release.py --non-interactive` and opt-in `--cleanup`.
- Hardened unattended Compose ownership preflight/teardown and aggregate cleanup verification.
- Added critical Grafana lifecycle alert/dashboard/runbook surfaces.
- Hardened local API startup ownership so early child exit/readiness timeout cannot strand stale PID metadata; cleanup targets only the exact spawned child.
- Hardened cross-invocation API shutdown against PID reuse with structured argv validation.
- Decoupled API health from process ownership; verified unhealthy processes are still safely cleaned up.
- Rejected zero/negative persisted PIDs before process lookup/signalling.
- Implemented truthful local stop teardown: missing Docker or non-zero `docker compose down` becomes `DemoError`; `Stopped.` is emitted only after successful teardown or explicit `--keep-stack`.
- Implemented independent local stop cleanup so API failure no longer suppresses owned Compose teardown; multiple failures are aggregated.

## Latest run — 2026-09-21 — independent local cleanup implementation

### Inspected at start

Read `progress.md` completely before deciding what to change. Inspected `scripts/demo_local.py` and `runtime/tests/test_demo_local_stop_lifecycle.py`, including the red independent-cleanup regressions from the preceding run.

### Finding

The red gate was valid: `demo_local.py::stop()` called `_stop_api()` before entering the Compose branch, so a controlled API-cleanup failure prevented `docker compose down` from being attempted. This violated the local ownership invariant and hid a second teardown failure when both components failed.

### Exact changes made

- Refactored `scripts/demo_local.py::stop()` to collect cleanup failures rather than aborting after the first one.
- StageGuard API cleanup remains the first attempt, but a `DemoError` from API cleanup is retained while requested Compose teardown still runs.
- Missing Docker and non-zero Compose teardown are retained as explicit partial-cleanup failures.
- When multiple cleanup responsibilities fail, one `DemoError` now reports every failure under `Local cleanup incomplete`.
- Preserved `--keep-stack`: Compose teardown is intentionally skipped when explicitly requested, while API cleanup failure still propagates.
- `Stopped.` is emitted only if every requested cleanup responsibility succeeds.
- Implementation commit: `367ff92de495da90acd7732caad293235510733b`.
- No credentials, cloud resources, live remediation targets, unrelated repositories, or GitHub Actions workflows were touched.

### Checks / results

- GitHub accepted the implementation update.
- Static inspection shows the implementation satisfies the focused regression contracts: Compose cleanup is attempted after API failure, simultaneous API/Compose failures are aggregated, and `--keep-stack` does not invoke Compose.
- No executable green-test claim is made: this connector environment does not expose a runnable checkout.

### Decisions

1. Cleanup components are independent responsibilities; teardown continues after a controlled failure in another owned component.
2. Cleanup remains fail-closed from the operator perspective: partial teardown is an error, never a success message.
3. Aggregated errors preserve both process-safety diagnostics and container teardown diagnostics without weakening PID ownership verification.
4. No CI workflow was added merely to execute these tests; avoid noisy Actions usage.

### Blockers / unknowns

- Focused lifecycle tests still require execution in a real checkout, including Windows command-line parsing validation.
- Historical full-suite failures/errors still need classification from an executable checkout.
- A live unattended Docker rehearsal is required after accumulated cleanup hardening.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.

## Single best next step

Execute `runtime/tests/test_demo_local_stop_lifecycle.py` together with the accumulated spawn/PID lifecycle suites on Linux and Windows; if green, run consolidated validation and an unattended `scripts/demo_release.py --non-interactive --cleanup` Docker rehearsal, then perform the pinned Grafana MCP `1.4.1` read-only smoke.

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
- Unattended cleanup independently attempts all runtime components it owns, verifies postconditions, and reports partial teardown as failure.
- API startup failure may terminate/reap only the exact `Popen` child created by that startup attempt.
- A persisted local API PID is never sufficient authority to signal a process; shutdown structurally verifies the live command signature first.
- Health reachability is not process ownership: a structurally verified unhealthy local API is still an owned process.
- Persisted PID metadata must be a strictly positive process ID before lookup or signal.
- Local stop must not report success if teardown of an owned Compose stack fails.

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
- Added regression coverage requiring interactive/local `stop` to surface Compose teardown failure instead of printing a false-success outcome.
- Implemented truthful local stop teardown: missing Docker or non-zero `docker compose down` now becomes `DemoError`; `Stopped.` is emitted only after successful teardown or explicit `--keep-stack`.

## Latest run — 2026-09-21 — local stop teardown truthfulness implementation

### Inspected at start

Read `progress.md` completely before deciding what to change. Inspected `scripts/demo_local.py` and `runtime/tests/test_demo_local_stop_lifecycle.py`, including the red regression gate created in the preceding run.

### Finding

The focused regression accurately captured a real operator-safety defect: `demo_local.py stop` attempted API cleanup first, but then swallowed both a missing Docker executable and non-zero `docker compose down`, finally printing `Stopped.` even though StageGuard-owned observability containers could still be running.

### Exact changes made

- Changed `scripts/demo_local.py::stop()` to preserve API-first cleanup and explicit `--keep-stack` behavior.
- A missing Docker executable during owned-stack teardown now raises `DemoError` with an explicit warning that the local stack may still be running.
- A non-zero Compose teardown now raises `DemoError` including the exit code and the same partial-cleanup warning.
- `Stopped.` is reached only when API cleanup completed and Compose teardown succeeded, or when the operator explicitly selected `--keep-stack`.
- Implementation commit: `559c152f950ce4805457fe4e34bf5d63bff77f64`.
- No credentials, cloud resources, live remediation targets, unrelated repositories, or GitHub Actions workflows were touched.

### Checks / results

- GitHub accepted the implementation update.
- Static inspection shows the implementation now satisfies the existing regression contract: `CalledProcessError` is converted to `DemoError` containing `Docker Compose teardown failed`, API cleanup remains first, and `--keep-stack` still bypasses Compose entirely.
- No executable green-test claim is made: the GitHub connector does not expose a runnable checkout in this automation environment.

### Decisions

1. Local teardown is an operational safety boundary, so partial cleanup must be surfaced as failure rather than treated as best-effort success.
2. API cleanup remains first so a Compose failure does not unnecessarily leave the StageGuard API process running.
3. `--keep-stack` remains the sole explicit path that intentionally leaves the telemetry stack running while reporting normal stop completion.
4. No CI workflow was added; accumulated lifecycle tests should be executed in a real checkout before expanding this area further.

### Blockers / unknowns

- Focused lifecycle tests still require execution in a real checkout, including Windows command-line parsing validation.
- Historical full-suite failures/errors still need classification from an executable checkout.
- A live unattended Docker rehearsal is required after accumulated cleanup hardening.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.

## Single best next step

Execute `runtime/tests/test_demo_local_stop_lifecycle.py` together with the accumulated spawn/PID lifecycle suites on Linux and Windows; if green, run consolidated validation and an unattended `scripts/demo_release.py --non-interactive --cleanup` Docker rehearsal, then perform the pinned Grafana MCP `1.4.1` read-only smoke.

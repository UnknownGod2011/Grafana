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
- Added a regression gate requiring interactive/local `stop` to surface Compose teardown failure instead of printing a false-success outcome.

## Latest run — 2026-09-21 — local stop teardown truthfulness gate

### Inspected at start

Read `progress.md` completely before deciding what to change. Inspected `scripts/demo_local.py` and the focused local process-lifecycle regressions.

### Finding

The unattended release cleanup path had already been hardened to fail closed, but the ordinary `demo_local.py stop` path still catches `FileNotFoundError` and `subprocess.CalledProcessError` from `docker compose down`, suppresses them, and then prints `Stopped.`. This can tell an operator cleanup succeeded while StageGuard-owned simulator/Prometheus/Grafana containers remain running. It is a correctness and operational-safety gap, not merely a UX issue.

### Exact changes made

- Added `runtime/tests/test_demo_local_stop_lifecycle.py`.
- Added a regression requiring a non-zero Compose teardown to surface as `DemoError` after API cleanup has been attempted.
- Added coverage proving `--keep-stack` continues to avoid Compose teardown entirely.
- Regression commit: `8b72c19f99d3f6b995c055940eb0985cc0e0e96f`.
- No credentials, cloud resources, live remediation targets, unrelated repositories, or GitHub Actions workflows were touched.

### Checks / results

- GitHub accepted the regression file.
- Static inspection shows the new failure-propagation test is intentionally red against the current `stop()` implementation because it currently suppresses `CalledProcessError`.
- No green test claim is made: this connector does not expose an executable checkout.

### Decisions

1. Cleanup commands are part of StageGuard's safety boundary and must report partial failure truthfully.
2. `--keep-stack` remains explicit operator intent and must never invoke Compose teardown.
3. The implementation should preserve API-first cleanup but convert Docker-not-found/non-zero teardown into a controlled `DemoError` rather than swallowing it.
4. This is kept local to `demo_local.py`; no noisy CI workflow is being added merely to exercise the gate.

### Blockers / unknowns

- Focused lifecycle tests still require execution in a real checkout, including Windows command-line parsing validation.
- Historical full-suite failures/errors still need classification from an executable checkout.
- A live unattended Docker rehearsal is required after accumulated cleanup hardening.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.

## Single best next step

Change `scripts/demo_local.py::stop()` so Docker Compose teardown failures raise a controlled `DemoError` and never print false success, make the new regression green, then execute the focused lifecycle suites on Linux/Windows before consolidated validation, unattended Docker cleanup rehearsal, and the pinned Grafana MCP `1.4.1` smoke.

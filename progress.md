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
- Successful Compose teardown must be verified by an empty project-container query, not inferred solely from `docker compose down` returning zero.

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
- Added a regression gate requiring post-`down` verification that the Compose project has no retained containers.

## Latest run — 2026-09-21 — post-Compose teardown verification gate

### Inspected at start

Read `progress.md` completely before deciding what to change. Inspected `scripts/demo_local.py` and the complete focused `runtime/tests/test_demo_local_stop_lifecycle.py` regression suite.

### Finding

The local stop path now propagates `docker compose down` failures correctly, but still treats a zero exit code from `compose down` as proof that the owned observability stack is gone. That is weaker than the unattended release cleanup contract: a successful command invocation can still leave project containers behind because of engine/plugin edge cases or partial cleanup. Printing `Stopped.` without checking project state can therefore remain operationally misleading.

### Exact changes made

- Extended `runtime/tests/test_demo_local_stop_lifecycle.py` with a red regression requiring a post-teardown `docker compose ps -q` verification query.
- Added a case where `compose down` returns zero but `compose ps -q` reports a retained StageGuard container; `stop()` must raise `DemoError` rather than report success.
- Added the complementary success contract: an empty captured `compose ps -q` result permits successful stop.
- Kept `--keep-stack` behavior unchanged; explicit retention must not invoke Compose at all.
- Regression commit: `295d9f79931093255f248f1d1e0cd1d2f16d87dd`.
- No credentials, cloud resources, live remediation targets, unrelated repositories, or GitHub Actions workflows were touched.

### Checks / results

- GitHub accepted the focused regression update.
- Static inspection confirms current `demo_local.py::stop()` invokes only `docker compose down` and does not yet perform the required verification query, so the two new tests intentionally establish a red implementation gate.
- No executable green-test claim is made: this connector environment does not expose a runnable checkout.

### Decisions

1. A zero exit status from a teardown command is evidence of command completion, not sufficient evidence of resource absence.
2. Verification remains scoped to the current Compose project via `docker compose ps -q`; it does not enumerate or touch unrelated Docker resources.
3. `--keep-stack` remains the explicit operator escape hatch and therefore intentionally bypasses teardown verification.
4. No CI workflow is added solely to run this gate; avoid noisy GitHub Actions usage.

### Blockers / unknowns

- The new post-teardown verification gate still needs implementation in `scripts/demo_local.py::stop()` and executable validation.
- Focused lifecycle tests still require execution in a real checkout, including Windows command-line parsing validation.
- Historical full-suite failures/errors still need classification from an executable checkout.
- A live unattended Docker rehearsal is required after accumulated cleanup hardening.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.

## Single best next step

Implement post-`docker compose down` verification in `scripts/demo_local.py::stop()` using captured `docker compose ps -q`, aggregate verification/query failures with any API cleanup failure, and only print `Stopped.` when the requested Compose project is verified empty; then execute the accumulated lifecycle suites before consolidated validation, unattended Docker cleanup rehearsal, and the pinned Grafana MCP `1.4.1` smoke.

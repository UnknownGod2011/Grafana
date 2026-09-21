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
- Cleanup should independently attempt all runtime components it owns and report partial teardown as failure.
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
- Implemented truthful local stop teardown: missing Docker or non-zero `docker compose down` becomes `DemoError`; `Stopped.` is emitted only after successful teardown or explicit `--keep-stack`.

## Latest run — 2026-09-21 — independent local cleanup regression gate

### Inspected at start

Read `progress.md` completely before deciding what to change. Inspected `scripts/demo_local.py`, `runtime/tests/test_demo_local_stop_lifecycle.py`, and the runtime test inventory.

### Finding

`demo_local.py::stop()` now reports Compose teardown failures truthfully, but cleanup is still serial in a way that violates the stronger cleanup invariant already used by unattended acceptance: if `_stop_api()` raises, `docker compose down` is never attempted. A stuck or unverifiable API therefore prevents cleanup of the independently owned observability stack. If both API and Compose cleanup fail, the operator also needs both failures rather than only the first one.

### Exact changes made

- Extended `runtime/tests/test_demo_local_stop_lifecycle.py` with a missing-Docker regression to cover the existing implementation contract explicitly.
- Added a red regression requiring Compose cleanup to be attempted even when StageGuard API cleanup fails.
- Added a red regression requiring API and Compose teardown failures to be aggregated into one controlled `DemoError` so neither failure is hidden.
- Preserved the explicit `--keep-stack` contract: it must never invoke Compose teardown.
- Regression commit: `86e60391389d0237b4f912fceb13a1f947049c00`.
- No credentials, cloud resources, live remediation targets, unrelated repositories, or GitHub Actions workflows were touched.

### Checks / results

- GitHub accepted the regression update.
- Static inspection confirms the new independent-cleanup regression is intentionally red against the current implementation because `_stop_api()` is called before the Compose branch without failure aggregation.
- The existing missing-Docker and Compose-nonzero behavior remains represented by focused tests.
- No executable green-test claim is made: this connector environment does not expose a runnable checkout.

### Decisions

1. Cleanup components owned by the local launcher are independent teardown responsibilities; failure of one must not suppress an attempt to clean another.
2. Multiple teardown failures must be aggregated for operators instead of losing the later failure or falsely reporting success.
3. `--keep-stack` remains an explicit operator choice and therefore exempts Compose from the independent cleanup attempt.
4. No CI workflow is being added merely to execute these tests; avoid noisy Actions usage.

### Blockers / unknowns

- Focused lifecycle tests still require execution in a real checkout, including Windows command-line parsing validation.
- Historical full-suite failures/errors still need classification from an executable checkout.
- A live unattended Docker rehearsal is required after accumulated cleanup hardening.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.

## Single best next step

Refactor `scripts/demo_local.py::stop()` to independently attempt API cleanup and owned Compose teardown, aggregate all cleanup failures into one `DemoError`, preserve `--keep-stack`, and emit `Stopped.` only when every requested cleanup responsibility succeeds; then execute the focused lifecycle suites on Linux/Windows before consolidated validation, unattended Docker rehearsal, and the pinned Grafana MCP `1.4.1` smoke.

# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the read-only runtime evidence plane. The implemented vertical slice includes deterministic telemetry, Prometheus/Loki/Grafana, official Grafana MCP access, bounded investigation and diagnosis, optional Gemini briefing, exact-revision approval, remediation adapters, telemetry-verified recovery, authenticated lifecycle state, checkpoint/audit integrity, operator UI, Cloud Run deployment hardening, watchdog observability, authenticated private metrics bridging, evidence-unavailable abstention, no-replay execution reconciliation, recovery-only Grafana rechecks, fixed-cardinality recovery observability, stdio-only Grafana MCP launchers, strict operator-API authentication/framing/protocol preflight, and a loopback reference remediation provider with idempotent writes plus read-only operation reconciliation.

Detailed older run history remains in Git history; this file keeps the current invariants, validation baseline, latest run, blockers, and next step.

## Core invariants

- Grafana/MCP is read-only evidence access; infrastructure-write credentials remain isolated.
- Gemini is advisory and cannot mutate diagnosis, approval, remediation, or recovery state.
- Required evidence unavailability prevents briefing, approval, and execution from becoming actionable.
- Approval is exact-revision-bound and single-use; provider acceptance never counts as recovery.
- Fresh Grafana telemetry is required to verify recovery.
- `recovery_unverified` can only use the recovery-only verification path and cannot replay provider remediation.
- Any remediation side effect followed by ambiguous checkpoint persistence remains behind the execution-uncertainty barrier, including local/non-reconciling adapters and process restarts during reconciliation.
- Execution uncertainty is resolved only through durable reload/reconciliation and fresh Grafana evidence; `/v1/execute` is never the recovery mechanism.
- Production adapters that support provider reconciliation must additionally resolve their server-owned operation ID before fresh evidence can release uncertainty.
- Durable checkpoint/audit failures fail closed; ambiguous provider execution blocks replay.
- Grafana MCP production and smoke launchers are stdio-only; network transports fail closed.
- Operator API and reference remediation provider reject ambiguous credential/body framing before mutation.
- Metric/Loki activation remains policy-owned and versioned; callers cannot supply arbitrary Grafana queries or datasource identities through the HTTP API.

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected Windows-specific permission test skipped.
- Focused core/API/UI suite from the last executable repository run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating the latest hardening/recovery work.
- Historical official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`; pinned `1.4.1` still requires a live smoke.
- Current committed consolidated tests remain blocked from repository execution in the automation runner; connector commits are not treated as passing tests.

## Run log — 2026-09-15 — local reconciliation restart barrier repair

### Inspected at start

Read `progress.md` completely first. Inspected `runtime/execution_safety.py`, `runtime/tests/test_execution_safety.py`, `runtime/tests/test_execution_reconciliation_gate.py`, `runtime/tests/test_local_execution_uncertainty_barrier.py`, and the checkpoint execution-phase contract.

### Defect found

The previous run correctly preserved local/non-reconciling remediation uncertainty after a post-side-effect checkpoint CAS loss. A second crash window remained: explicit local reconciliation persists a `dispatching` checkpoint before collecting fresh Grafana evidence. If the process crashed in that gap, restart ignored the durable `dispatching` phase solely because the adapter was local/non-reconciling. The stale approval could therefore become executable again even though the original local side effect may already have happened. This violated the no-replay invariant across process restart.

### Exact changes made

1. Hardened restored-approval guarding in `runtime/execution_safety.py`.
2. Production/reconciling adapters retain the existing fail-closed legacy behavior when execution-phase metadata is unavailable.
3. Local adapters retain historical semantics for legacy/non-phase-capable stores and for durable `approved` checkpoints, where no side effect is proven to have started.
4. Local adapters backed by a phase-capable store now treat durable `dispatching`/ambiguous pending approvals as execution-uncertain on restart, derive the stable operation reference, and require explicit reconciliation plus fresh Grafana evidence before the barrier can clear.
5. Added a restart regression to `runtime/tests/test_local_execution_uncertainty_barrier.py` that models a crash after a local reconciliation attempt persisted `dispatching`; it proves `/execute` remains blocked, no local remediation is replayed, and reconciliation is the only release path.

Commits:
- `b44bd0188c229dc7c73f22ac73a1e83500b2c59e` — preserve local reconciliation barrier across restart
- `4f3d5ed9d3b998ddde75a89b2ff472f33cb2ee93` — test local reconciliation crash restart barrier

### Checks / results

- Authenticated GitHub reads/writes succeeded against `UnknownGod2011/Grafana`.
- Statically cross-checked the change against the existing restored-local-pending-approval test: non-phase-capable local stores remain synchronized, preserving that contract.
- Statically cross-checked production behavior: reconciling adapters still fail closed when phase metadata is absent and still accept a durable `approved` phase as safe to execute.
- No GitHub Actions workflow was created or triggered. No credentials, Grafana Cloud, Gemini, Google Cloud resources, real remediation provider, or unrelated repository was touched.
- This run still did not have an executable repository checkout, so the new regression and consolidated suite are not claimed green.

### Decisions

1. A durable `dispatching` phase is safety evidence independent of whether the remediation adapter offers a provider lookup API.
2. Local adapters may skip provider reconciliation, but they may not skip the no-replay barrier or fresh Grafana evidence after a persisted ambiguous dispatch phase.
3. Legacy local pending approvals remain executable because local ordinary execution does not persist a pre-dispatch barrier; changing that behavior without durable evidence would be speculative and backward-incompatible.
4. Continue prioritizing concrete lifecycle contradictions and historical-suite triage over additional protocol hardening.

### Blockers / unknowns

- Consolidated execution of recent execution-safety/remediation/recovery regressions is still required.
- Historical full-suite failures/errors still need classification from an executable checkout.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- Disposable private Cloud Run acceptance still requires suitable credentials/environment and Docker.

## Single best next step

Run `runtime.tests.test_local_execution_uncertainty_barrier`, `runtime.tests.test_execution_reconciliation_gate`, and `runtime.tests.test_execution_safety` first from an executable checkout. If green, run remediation transport/receiver and recovery/no-replay suites, then the full unittest suite and fix the highest-severity genuine remaining defect. If checkout remains unavailable, inspect the persisted reconciliation/audit transition for another concrete crash-consistency contradiction rather than adding speculative hardening.

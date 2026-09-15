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
- Any remediation side effect followed by ambiguous checkpoint persistence remains behind the execution-uncertainty barrier, including local/non-reconciling adapters.
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

## Run log — 2026-09-15 — local remediation no-replay barrier repair

### Inspected at start

Read `progress.md` completely first. Inspected `runtime/execution_safety.py` and `runtime/tests/test_execution_safety.py` through authenticated GitHub reads, focusing on the prior next step: concrete lifecycle defects around execution uncertainty and reconciliation.

### Defect found

A local/non-reconciling remediation adapter could perform its side effect and then lose the checkpoint CAS. `execute_approved()` correctly marked execution uncertain. However, `reload_checkpoint_after_conflict()` immediately cleared that uncertainty when `requires_operation_reconciliation` was false. This released the no-replay barrier solely because the adapter lacked a provider lookup API, even though the side effect had already occurred and the durable winner still contained the stale approval.

The existing `test_local_adapter_can_resolve_via_fresh_grafana_evidence_without_provider_lookup` already encoded the safer intended behavior: local adapters should use the reconciliation entry point and fresh Grafana evidence, without a provider lookup and without replaying remediation. The implementation contradicted that contract.

### Exact changes made

1. Updated `reload_checkpoint_after_conflict()` in `runtime/execution_safety.py` to preserve the prior server-owned operation ID before clearing in-memory uncertainty.
2. For local/non-reconciling adapters with a still-pending durable approval, reload now restores `execution_uncertain`, marks the durable winner as reloaded, and records `phase_unavailable` rather than silently returning to synchronized state.
3. The existing `_provider_reconciliation()` behavior for local adapters remains intentionally `not_found`; this means the explicit reconciliation path can proceed directly to fresh Grafana investigation without pretending a provider lookup exists.
4. Added `runtime/tests/test_local_execution_uncertainty_barrier.py`. It proves that after a local side effect + checkpoint CAS loss, durable reload does not permit `/execute` replay, remediation call count stays exactly one, and only explicit reconciliation plus fresh evidence releases uncertainty and clears the stale approval.

Commits:
- `26a7eb4e1143545c2be885ac9520f4dfed5702ed` — fix local remediation uncertainty reload barrier
- `51055719e7ad1cc7a1a11cd470ac32271141776a` — add local no-replay reload regression

### Checks / results

- Authenticated GitHub reads/writes succeeded against `UnknownGod2011/Grafana`.
- Statically cross-checked the repaired path against the existing local-adapter reconciliation test and the production-adapter path.
- The change is deliberately limited to the case where execution was already uncertain, durable reload still has a pending approval, and the adapter does not expose provider reconciliation.
- No GitHub Actions workflow was created or triggered. No credentials, Grafana Cloud, Gemini, Google Cloud resources, real remediation provider, or unrelated repository was touched.
- This run did not obtain an executable checkout, so the new regression and consolidated suite are not claimed green.

### Decisions

1. Lack of a provider reconciliation API is not evidence that an already-dispatched side effect did not happen.
2. Local adapters resolve post-dispatch persistence ambiguity through explicit reconciliation + fresh Grafana evidence, never by replaying remediation.
3. Keep the stricter provider-state requirement for production adapters that declare operation reconciliation support.
4. Continue prioritizing historical-suite defect triage over speculative hardening.

### Blockers / unknowns

- Consolidated execution of recent execution-safety/remediation/recovery regressions is still required.
- Historical full-suite failures/errors still need classification from an executable checkout.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- Disposable private Cloud Run acceptance still requires suitable credentials/environment and Docker.

## Single best next step

Run `runtime.tests.test_local_execution_uncertainty_barrier`, `runtime.tests.test_execution_reconciliation_gate`, and `runtime.tests.test_execution_safety` first from an executable checkout. If green, run remediation transport/receiver and recovery/no-replay suites, then the full unittest suite and fix the highest-severity genuine remaining defect. If checkout remains unavailable, statically triage the next concrete lifecycle inconsistency rather than adding speculative hardening.

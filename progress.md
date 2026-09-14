# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the read-only runtime evidence plane. The implemented vertical slice includes deterministic telemetry, Prometheus/Loki/Grafana, official Grafana MCP access, bounded investigation and diagnosis, optional Gemini briefing, exact-revision approval, remediation adapters, telemetry-verified recovery, authenticated lifecycle state, checkpoint/audit integrity, operator UI, Cloud Run deployment hardening, watchdog observability, authenticated private metrics bridging, evidence-unavailable abstention, no-replay execution reconciliation, recovery-only Grafana rechecks, fixed-cardinality recovery observability, stdio-only Grafana MCP launchers, strict operator-API authentication/framing/protocol preflight, and a loopback reference remediation provider with idempotent writes plus read-only operation reconciliation.

Detailed older run history remains in Git history; this file keeps the current invariants, validation baseline, latest run, blockers, and next step.

## Core invariants

- Grafana/MCP is read-only evidence access; infrastructure-write credentials remain isolated.
- StageGuard's production Grafana MCP adapters and smoke client are local stdio-only subprocess clients; network MCP transports fail closed.
- Investigation and recovery accept only finite non-boolean numeric metric evidence; malformed samples become unavailable and can never prove diagnosis/recovery.
- Loki corroboration validates bounded evidence envelopes, windows, shapes, scope, and event identity.
- Gemini is advisory and cannot mutate diagnosis, approval, remediation, or recovery state.
- Required evidence unavailability prevents briefing, approval, and execution from becoming actionable.
- Approval is exact-revision-bound and single-use; provider acceptance never counts as recovery.
- Fresh Grafana telemetry is required to verify recovery.
- `recovery_unverified` can only use the recovery-only verification path and cannot replay provider remediation.
- Execution uncertainty is resolved only through durable reload/reconciliation and fresh Grafana evidence; `/v1/execute` is never the recovery mechanism.
- Reconciliation is the sole intentional escape from the execution-uncertainty mutation barrier after durable reload; ordinary lifecycle mutations remain blocked.
- Durable checkpoint/audit failures fail closed; ambiguous provider execution blocks replay.
- Provider reconciliation is read-only, keyed only by the server-owned StageGuard operation ID, and never returns mutation action/production/target detail.
- Provider `not_found` is trusted only when the exact requested lookup URL returns the exact bounded `{operation_id, state:not_found}` contract; generic/malformed/proxy 404s remain `unknown`.
- Operator-API credentials are bounded and duplicate credential-bearing headers fail closed.
- Mutating operator requests reject every `Transfer-Encoding`, duplicate `Content-Length`, unknown/query-bearing mutation routes, and every `Expect` header before body mutation.
- The loopback reference remediation provider rejects duplicate `Authorization` and `Idempotency-Key` headers, duplicate/ambiguous `Content-Length`, every `Transfer-Encoding`, and non-JSON media types before touching its idempotency registry.
- Metric/Loki activation remains policy-owned and versioned; callers cannot supply arbitrary Grafana queries or datasource identities through the HTTP API.
- Recovery observability remains fixed-cardinality and provider-detail-free.
- The browser cockpit trusts the authenticated server-produced recovery contract and fails closed on malformed/inconsistent lifecycle state.

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected Windows-specific permission test skipped.
- Focused core/API/UI suite from the last executable repository run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating the latest hardening/recovery work.
- Historical official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`; pinned `1.4.1` still requires a live smoke.
- Identity focused tests were previously reconstructed and executed independently: 14/14 passed.
- Operator request-framing and protocol-preflight boundaries were previously exercised through real `BaseHTTPRequestHandler`/raw-socket paths and behaved fail-closed.
- Reference remediation reconciliation was previously reconstructed and exercised over real loopback HTTP: missing -> 404/not_found, POST -> accepted, GET -> accepted, bad bearer -> 401, conflicting reuse -> 409.
- Authoritative reconciliation-404 parsing was independently exercised with real `urllib.error.HTTPError` objects; only the exact same-URL provider contract resolved to `not_found`.
- Current committed consolidated tests remain blocked from repository execution because this runner cannot resolve `github.com` for a fresh checkout. Connector commits are not treated as passing tests.

## Run log — 2026-09-15 — execution-uncertainty reconciliation gate repair

### Inspected at start

Read this `progress.md` completely before selecting work. Inspected repository metadata and then statically triaged the no-replay/restart lifecycle seam through authenticated GitHub reads, including:

- `runtime/execution_safety.py`
- `runtime/anchored_execution_safety.py`
- `runtime/incident_service.py`
- `runtime/tests/test_execution_safety.py`
- the runtime/test directory inventory relevant to execution safety

Attempted a fresh shallow checkout and the focused remediation tests first, as required by the prior next step. Checkout still fails before test execution with `Could not resolve host: github.com`.

### Defect found

`ExecutionSafeIncidentService.reconcile_execution_uncertainty()` required `_execution_uncertain == True` and `_execution_reloaded == True`, then immediately called `_require_checkpoint_consistency()`. That same consistency gate intentionally raises whenever execution is uncertain unless `_allow_uncertainty_investigation` is set. As a result, the reconciliation path deadlocked itself after reload and could fail before provider reconciliation was attempted.

This contradicted the existing intended contract already encoded in `runtime/tests/test_execution_safety.py`: after durable reload, reconciliation should query the provider exactly once, collect fresh Grafana evidence, clear the stale approval, and release the uncertainty barrier without replaying the provider action.

### Exact changes made

1. Added `_require_reconciliation_checkpoint_consistency()` in `runtime/execution_safety.py`.
2. The helper temporarily bypasses only the local execution-uncertainty guard while still invoking the complete cooperative `_require_checkpoint_consistency()` chain, so anchored/in-flight checks, audit-integrity checks, and checkpoint-conflict checks still run.
3. The bypass flag is restored in `finally` before provider lookup or investigation begins; it does not globally weaken ordinary lifecycle mutation blocking.
4. Changed `reconcile_execution_uncertainty()` to use this reconciliation-specific consistency gate after durable reload.
5. Added `runtime/tests/test_execution_reconciliation_gate.py`, covering the exact invariant: reconciliation is blocked before reload, ordinary execution remains blocked after reload, provider dispatch is not replayed, then reconciliation is allowed exactly once and clears stale approval/uncertainty after fresh evidence.

Commits:
- `412a55f8910cb0792aaff8472dd5efdf4f222762` — fix execution uncertainty reconciliation gate
- `93c63475cf8a7b62697c991dbac2721c2359b95d` — add reconciliation gate regression

### Checks / results

- Authenticated GitHub connector reads/writes succeeded against `UnknownGod2011/Grafana`.
- Re-read the committed reconciliation section and confirmed the new helper restores `_allow_uncertainty_investigation` with `finally`, then reconciliation separately enables it only for the fresh investigation.
- Cross-checked the base `IncidentService._require_checkpoint_consistency()` contract: audit-integrity failure and unresolved checkpoint conflicts remain fail-closed.
- Cross-checked the anchored override: an active provider/recovery operation still blocks reconciliation through the cooperative consistency chain.
- Existing `test_execution_safety.py` already contains multiple success expectations that exercise the repaired path, in addition to the new focused regression.
- Fresh local checkout remains blocked by DNS (`Could not resolve host: github.com`), so neither the new regression nor the existing execution-safety suite executed from the committed repository. No green claim is made.
- No GitHub Actions workflow was created or triggered, and no Grafana Cloud, Gemini, Google Cloud, real remediation provider, credentials, or unrelated repositories were touched.

### Decisions

1. Treat reconciliation as a narrowly privileged lifecycle operation, not as a general weakening of the execution-uncertainty barrier.
2. Preserve dynamic/cooperative consistency checks rather than directly calling `IncidentService._require_checkpoint_consistency()`, so production anchored compositions retain their additional in-flight safety guard.
3. Keep provider lookup and fresh Grafana investigation under the existing no-replay flow; this change only repairs reachability of that flow.
4. Do not add or trigger GitHub Actions merely to compensate for this runner's transient DNS limitation.

### Blockers / unknowns

- This runner still cannot resolve `github.com` for a fresh checkout, so committed execution-safety/remediation/recovery suites cannot execute here.
- The historical full-suite failures/errors still need consolidated execution; this run identified one concrete defect likely contributing to those failures.
- Recent audit/checkpoint/recovery/Grafana/MCP/auth/framing/provider-reconciliation regressions still require consolidated execution.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- The real disposable private Cloud Run acceptance still requires a private StageGuard service, least-privilege invoker identity, and Docker.

## Single best next step

**When checkout becomes executable, run `runtime.tests.test_execution_reconciliation_gate` and `runtime.tests.test_execution_safety` first, then `runtime.tests.test_remediation_receiver`, `runtime.tests.test_http_remediation_transport`, and `runtime.tests.test_execution_safety_http_transport`. If those are green, run the focused recovery/no-replay suite and then the full unittest suite, classifying every remaining historical failure/error. If checkout remains unavailable, continue connector-level static triage for another concrete lifecycle defect rather than adding speculative hardening.**

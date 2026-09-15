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

## Run log — 2026-09-15 — reconciliation audit observability triage

### Inspected at start

Read `progress.md` completely first. Inspected `runtime/execution_safety.py` and the audit/checkpoint implementation in `runtime/incident_service.py`, with particular attention to reconciliation attempt persistence, append-before-CAS audit lineage, restart behavior, and operator timeline projection.

### Findings

1. The reconciliation attempt intentionally appends audit evidence before checkpoint CAS, matching StageGuard's authenticated candidate-lineage design; this is not itself a defect.
2. The persisted `dispatching` reconciliation barrier remains correctly bound to the checkpoint/audit head when the audit chain is available.
3. A concrete observability gap remains: reconciliation events carry bounded `result` and `reason` payloads internally, but `_timeline_event()` currently exposes no payload fields for the dynamic `remediation_reconciliation_*` event types. Operators can see the encoded event type but not the structured reconciliation state/reason through the normal timeline projection. This should be repaired with an explicit bounded allowlist and regression coverage; operation IDs and provider details must remain excluded.

### Checks / results

- Attempted the requested executable checkout and focused suite with `git clone` followed by `python -m unittest runtime.tests.test_local_execution_uncertainty_barrier runtime.tests.test_execution_reconciliation_gate runtime.tests.test_execution_safety`.
- Checkout failed before tests could run because the runner still cannot resolve `github.com`; no test-green claim is made.
- Authenticated GitHub connector reads/writes remain functional.
- No GitHub Actions workflow was created or triggered. No credentials, Grafana Cloud, Gemini, Google Cloud resources, remediation provider, or unrelated repository was touched.
- During this run an incomplete connector file replacement was detected immediately and the branch was restored to the exact prior commit `ee26a9c9706556093037d0f59f28397d530b4d99` before any further repository work. The repository implementation was therefore not left in the transient broken state.

### Decisions

1. Do not alter append-before-CAS audit ordering without evidence of an authenticated-lineage defect; it is an intentional concurrency design.
2. Reconciliation timeline payloads should expose only the already-bounded `result` and `reason` fields. Never expose operation IDs, provider response bodies, targets, credentials, or arbitrary metadata.
3. Continue prioritizing executable suite triage as soon as checkout works; avoid speculative lifecycle changes while the consolidated regressions remain unexecuted.

### Blockers / unknowns

- Consolidated execution of recent execution-safety/remediation/recovery regressions is still required.
- Historical full-suite failures/errors still need classification from an executable checkout.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- Disposable private Cloud Run acceptance still requires suitable credentials/environment and Docker.

## Single best next step

Implement the bounded reconciliation timeline projection (`result` + `reason` only) with a focused regression, then execute the local uncertainty, reconciliation-gate, and execution-safety suites as soon as repository checkout is available. If those are green, proceed to remediation transport/receiver and recovery/no-replay suites, then classify the historical full-suite failures.

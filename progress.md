# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the read-only runtime evidence plane. The implemented vertical slice includes deterministic telemetry, Prometheus/Loki/Grafana, official Grafana MCP access, bounded investigation and diagnosis, optional Gemini briefing, exact-revision approval, remediation adapters, telemetry-verified recovery, authenticated lifecycle state, checkpoint/audit integrity, operator UI, Cloud Run deployment hardening, watchdog observability, authenticated private metrics bridging, evidence-unavailable abstention, no-replay execution reconciliation, recovery-only Grafana rechecks, fixed-cardinality recovery observability, stdio-only Grafana MCP launchers, strict operator-API authentication/framing/protocol preflight, and a loopback reference remediation provider with idempotent writes plus read-only operation reconciliation.

Detailed older run history remains in Git history; this file keeps current invariants, validation baseline, latest run, blockers, and next step.

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
- Reconciliation timeline projection is bounded to canonical event names whose encoded stage/result/reason agree with validated payload values; operation IDs, provider bodies, targets, credentials, and arbitrary audit metadata must never be exposed.

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected Windows-specific permission test skipped.
- Focused core/API/UI suite from the last executable repository run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating latest hardening/recovery work.
- Historical official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`; pinned `1.4.1` still requires a live smoke.
- Current committed consolidated tests remain blocked from repository execution in this runner; connector commits are not treated as passing tests.

## Run log — 2026-09-15 — canonical reconciliation timeline validation

### Inspected at start

Read `progress.md` completely first. Inspected `runtime/incident_service.py`, `runtime/timeline_projection.py`, `runtime/execution_safety.py`, and the focused timeline projection tests. Confirmed reconciliation audit event names are generated canonically as `remediation_reconciliation_<stage>.<result>.<reason>` with bounded stages `attempt`/`recovered`, while the new projector previously trusted only the prefix and independently bounded payload values.

### Changes made

1. Hardened `runtime/timeline_projection.py` so reconciliation projection now requires exactly three canonical suffix components: stage, result, and reason.
2. Added an explicit bounded stage set (`attempt`, `recovered`).
3. Required the result/reason encoded in the audit event name to exactly equal the validated payload values. Contradictory or malformed audit records now fail closed to `{}` rather than projecting potentially misleading operator semantics.
4. Kept the disclosure boundary unchanged: only `result` and `reason` can be returned; provider operation IDs, bodies, targets, credentials, and arbitrary metadata remain excluded.
5. Expanded `runtime/tests/test_timeline_projection.py` across both stages, the complete current result/reason matrix, future values, unknown stages, contradictory event/payload pairs, and malformed/noncanonical event names.

### Checks / results

- Authenticated GitHub connector reads/writes succeeded.
- The large `incident_service.py` blob can now be read completely through the connector, but the available write primitive still replaces the entire file rather than applying a minimal patch. I did not perform a risky whole-file replacement solely to add the two-line projector integration.
- Current tests were not executed in a repository checkout, so no new green claim is made.
- No GitHub Actions workflow was created or triggered. No credentials, Grafana Cloud, Gemini, Google Cloud resources, remediation provider, or unrelated repository was touched.

### Decisions

1. Treat reconciliation audit event names as part of the integrity contract, not merely a prefix marker.
2. Require event-name/payload agreement before operator-visible projection; this makes corruption and future schema drift fail closed.
3. Do not risk a whole-file replacement of `incident_service.py` for a tiny integration while a safe patch-capable checkout is unavailable.
4. Continue prioritizing executable suite triage over speculative lifecycle changes.

### Blockers / unknowns

- `reconciliation_timeline_payload()` still needs to be wired into `incident_service._timeline_event` and covered through the public `audit_timeline()` path.
- Consolidated execution of recent execution-safety/remediation/recovery regressions is still required.
- Historical full-suite failures/errors still need classification from an executable checkout.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- Disposable private Cloud Run acceptance still requires suitable credentials/environment and Docker.

## Single best next step

Wire `reconciliation_timeline_payload()` into `incident_service._timeline_event` using a safe patch-capable checkout or equivalent minimal-edit path, add a public `audit_timeline()` regression, then execute the local uncertainty, reconciliation-gate, execution-safety, remediation transport/receiver, and recovery/no-replay suites before further lifecycle changes.

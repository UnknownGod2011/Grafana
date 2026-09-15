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

## Run log — 2026-09-15 — reconciliation integration ownership verified

### Inspected at start

Read `progress.md` completely first. Re-inspected the complete `runtime/incident_service.py` blob, `runtime/timeline_projection.py`, and the execution-safety layer that owns provider reconciliation. Confirmed the public `audit_timeline()` implementation and `_timeline_event()` projector live in the base `IncidentService`, while reconciliation lifecycle state/events are implemented by `ExecutionSafeIncidentService` in `runtime/execution_safety.py`.

### Changes made

No runtime behavior was changed. The inspection resolved an important ownership ambiguity before editing lifecycle code: reconciliation is intentionally layered above the base service, but operator timeline projection is centralized in the base service. Therefore the correct minimal integration remains to import `reconciliation_timeline_payload` into `incident_service.py` and invoke it from `_timeline_event()` only when the static allowlist does not own the event. This preserves existing event projections and lets canonical reconciliation events expose only validated `result`/`reason`.

### Checks / results

- Authenticated GitHub connector reads succeeded, including complete blob retrieval for `runtime/incident_service.py`.
- Confirmed `IncidentService.audit_timeline()` funnels every selected audit record through `_timeline_event()`.
- Confirmed `ExecutionSafeIncidentService` is the reconciliation-owning subclass and imports the base service rather than replacing its timeline projector.
- Confirmed `runtime/timeline_projection.py` still fails closed unless reconciliation event stage/result/reason are canonical and agree with payload values.
- No tests were executed and no green claim is made.
- No GitHub Actions workflow was created or triggered. No credentials, Grafana Cloud, Gemini, Google Cloud resources, remediation provider, or unrelated repository was touched.

### Decisions

1. Integrate at the base `_timeline_event()` boundary rather than duplicating `audit_timeline()` in the execution-safety subclass; one projection boundary avoids divergent disclosure policy.
2. Static event allowlists remain authoritative for existing event types; reconciliation projection is a narrow fallback, not a general dynamic-payload mechanism.
3. Do not perform a manual whole-file replacement of lifecycle-critical `incident_service.py` through the connector for a two-line change when no executable checkout is available to verify the reconstructed file.

### Blockers / unknowns

- `reconciliation_timeline_payload()` still needs to be wired into `incident_service._timeline_event` and covered through the public `audit_timeline()` path.
- Consolidated execution of recent execution-safety/remediation/recovery regressions is still required.
- Historical full-suite failures/errors still need classification from an executable checkout.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- Disposable private Cloud Run acceptance still requires suitable credentials/environment and Docker.

## Single best next step

Use the first available patch-capable checkout/edit path to make the now-verified minimal base-service integration: import `reconciliation_timeline_payload`, use it as the fail-closed fallback in `_timeline_event()`, add a public `audit_timeline()` regression proving canonical reconciliation visibility plus operation/provider/target/credential non-disclosure, run focused timeline tests, then execute the local uncertainty, reconciliation-gate, execution-safety, remediation transport/receiver, and recovery/no-replay suites before further lifecycle changes.

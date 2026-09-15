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

## Run log — 2026-09-15 — reconciliation projection contract coverage

### Inspected at start

Read `progress.md` completely first. Re-read the current `runtime/incident_service.py` timeline projection and public `audit_timeline()` path in bounded line ranges, plus the complete `runtime/timeline_projection.py` helper. Confirmed the integration point has not moved: unknown event types still receive an empty payload in `_timeline_event()`, while reconciliation projection remains a separate fail-closed helper.

### Changes made

- Added `runtime/tests/test_timeline_projection_contract.py`.
- Added focused contract coverage proving a canonical reconciliation event exposes only bounded `result` and `reason` fields even when the durable audit payload contains an operation ID, provider body, target, or credential-like field.
- Added negative coverage for event/payload contradictions, unknown future result/stage values, and malformed event names.
- No lifecycle behavior was changed in this run; the public `audit_timeline()` wiring remains pending.

### Checks / results

- Authenticated GitHub connector reads and commit writes succeeded.
- The new test file was committed as `e2c91919f5f9fc1130b0ef3d52dd2eef64331bdd`.
- Tests were not executed in this runner, so no new green claim is made.
- No GitHub Actions workflow was created or triggered. No credentials, Grafana Cloud, Gemini, Google Cloud resources, remediation provider, or unrelated repository was touched.

### Decisions

1. Keep the reconciliation disclosure boundary independently regression-tested before wiring it into the public timeline path.
2. Continue to avoid replacing the complete lifecycle-critical `incident_service.py` through a whole-file contents write solely for a two-line integration while a patch-capable checkout is unavailable.
3. Preserve existing static timeline projections as authoritative; reconciliation projection should be fallback-only.

### Blockers / unknowns

- `incident_service._timeline_event()` still needs the reconciliation projector fallback, followed by a public `audit_timeline()` regression proving the same non-disclosure contract end-to-end.
- Consolidated execution of recent execution-safety/remediation/recovery regressions is still required.
- Historical full-suite failures/errors still need classification from an executable checkout.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- Disposable private Cloud Run acceptance still requires suitable credentials/environment and Docker.

## Single best next step

Land the minimal `incident_service.py` reconciliation projector fallback through a patch-capable edit path and add a public `audit_timeline()` non-disclosure regression; then run the focused timeline tests and the local uncertainty, reconciliation-gate, execution-safety, remediation transport/receiver, and recovery/no-replay suites before further lifecycle changes.

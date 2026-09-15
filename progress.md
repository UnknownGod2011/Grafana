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
- Reconciliation timeline parsing rejects oversized durable event names before splitting/parsing them.

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected Windows-specific permission test skipped.
- Focused core/API/UI suite from the last executable repository run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating latest hardening/recovery work.
- Historical official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`; pinned `1.4.1` still requires a live smoke.
- Current committed consolidated tests remain blocked from repository execution in this runner; connector commits are not treated as passing tests.

## Run log — 2026-09-15 — bounded reconciliation timeline parser

### Inspected at start

Read `progress.md` completely first. Re-read the current `runtime/incident_service.py` timeline projection in a bounded range, the complete `runtime/timeline_projection.py` helper, and the focused timeline projection contract tests. Confirmed the public integration point remains unchanged: `_timeline_event()` still uses only the static allowlist, while reconciliation projection remains a separate fail-closed helper.

### Changes made

- Hardened `runtime/timeline_projection.py` with an explicit maximum reconciliation event-type length before suffix splitting/parsing. Durable audit data may be corrupted or externally supplied, so the operator projection no longer performs parser work on arbitrarily large reconciliation-looking names.
- Updated the helper contract documentation to include oversized input in its fail-closed semantics.
- Added a focused regression in `runtime/tests/test_timeline_projection_contract.py` proving a 4 KiB reconciliation-looking event name is rejected with an empty projection.
- No lifecycle or remediation behavior was changed. Public `audit_timeline()` wiring remains pending.

### Checks / results

- Authenticated GitHub connector reads and writes succeeded.
- Parser hardening committed as `0633847f20eb8d7bbc631dd4437ae30bed30316e`.
- Oversized-input regression committed as `dcdf5bc8b015759616374c55a1b5711ca2bc27bf`.
- Tests were not executed in this runner, so no new green claim is made.
- No GitHub Actions workflow was created or triggered. No credentials, Grafana Cloud, Gemini, Google Cloud resources, remediation provider, or unrelated repository was touched.

### Decisions

1. Treat durable audit event names as untrusted bounded input at the operator projection boundary.
2. Keep reconciliation disclosure fail-closed and limited to canonical `result`/`reason` values.
3. Continue avoiding a complete replacement of lifecycle-critical `incident_service.py` solely for the small projector fallback while a safe patch-capable edit path is unavailable.

### Blockers / unknowns

- `incident_service._timeline_event()` still needs the reconciliation projector fallback, followed by a public `audit_timeline()` regression proving the same non-disclosure contract end-to-end.
- Consolidated execution of recent execution-safety/remediation/recovery regressions is still required.
- Historical full-suite failures/errors still need classification from an executable checkout.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- Disposable private Cloud Run acceptance still requires suitable credentials/environment and Docker.

## Single best next step

Land the minimal `incident_service.py` reconciliation projector fallback through a patch-capable edit path and add a public `audit_timeline()` non-disclosure regression; then run the focused timeline tests and the local uncertainty, reconciliation-gate, execution-safety, remediation transport/receiver, and recovery/no-replay suites before further lifecycle changes.

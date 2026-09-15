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
- Operator timeline disclosure is allowlist-based. Canonical remediation reconciliation may expose only bounded `result` and `reason`; operation IDs, provider bodies, targets, credentials, and arbitrary audit metadata must never be exposed.
- Reconciliation timeline parsing rejects oversized durable event names before splitting/parsing them.

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected Windows-specific permission test skipped.
- Focused core/API/UI suite from the last executable repository run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating latest hardening/recovery work.
- Historical official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`; pinned `1.4.1` still requires a live smoke.
- Current committed consolidated tests remain blocked from repository execution in this runner; connector commits are not treated as passing tests.

## Run log — 2026-09-15 — centralized operator timeline disclosure policy

### Inspected at start

Read `progress.md` completely first. Re-read the current `runtime/incident_service.py` timeline projection, `runtime/timeline_projection.py`, and focused timeline projection contract tests. Confirmed `_timeline_event()` still owns the public `audit_timeline()` projection and currently uses only its local static allowlist.

### Changes made

- Added `timeline_payload()` to `runtime/timeline_projection.py` as the single fail-closed payload disclosure policy intended for the public timeline path.
- Existing lifecycle events preserve explicit static field allowlists; unknown events expose no payload by default.
- Canonical remediation reconciliation events are the sole dynamic fallback and still pass through strict stage/result/reason validation.
- Added tests proving static allowlist behavior, canonical reconciliation delegation, unknown-event non-disclosure, credential/provider metadata non-disclosure, and invalid-input fail-closed behavior.
- Retained the existing bounded reconciliation event-name parser and semantic event-name/payload consistency checks.

### Checks / results

- Authenticated GitHub connector reads and writes succeeded.
- Central projector committed as `284355fc86ccccb381ca8210c4ef113aeaf6a762`.
- Contract tests committed as `43d97dbc4e6755af70b6a7dcca4101bbc6c10f4c`.
- A fresh local checkout was attempted and still failed with `Could not resolve host: github.com`; tests therefore were not executed and no new green claim is made.
- No GitHub Actions workflow was created or triggered. No credentials, Grafana Cloud, Gemini, Google Cloud resources, remediation provider, or unrelated repository was touched.

### Decisions

1. Centralize all operator timeline payload disclosure in one helper rather than adding a reconciliation-only special case directly to lifecycle code.
2. Preserve fail-closed behavior for unknown/future event types.
3. Keep dynamic reconciliation projection strictly narrower than durable audit payloads.
4. Do not rewrite lifecycle-critical `incident_service.py` from a large connector payload without executable checkout validation; the remaining integration is now a minimal import plus helper call.

### Blockers / unknowns

- `incident_service._timeline_event()` still needs to call `timeline_payload(event.event_type, event.payload, _TIMELINE_PAYLOAD_FIELDS)`, followed by a public `audit_timeline()` non-disclosure regression.
- Consolidated execution of recent execution-safety/remediation/recovery regressions is still required.
- Historical full-suite failures/errors still need classification from an executable checkout.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- Disposable private Cloud Run acceptance still requires suitable credentials/environment and Docker.

## Single best next step

Wire `timeline_payload()` into `incident_service._timeline_event()` through a safely validated edit path, add an end-to-end public `audit_timeline()` reconciliation non-disclosure regression, and execute the focused timeline suite before further lifecycle changes.

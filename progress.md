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
- Operator timeline disclosure is allowlist-based. Canonical remediation reconciliation may expose only bounded `result` and `reason`; operation IDs, provider bodies, targets, credentials, arbitrary audit metadata, and raw actor identities must never be exposed.
- Reconciliation timeline parsing rejects oversized durable event names before splitting/parsing them.

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected Windows-specific permission test skipped.
- Focused core/API/UI suite from the last executable repository run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating latest hardening/recovery work.
- Historical official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`; pinned `1.4.1` still requires a live smoke.
- Current committed consolidated tests remain blocked from repository execution in this runner; connector commits are not treated as passing tests.

## Run log — 2026-09-15 — public reconciliation timeline integration

### Inspected at start

Read `progress.md` completely first. Re-read the complete exact blob for `runtime/incident_service.py`, the centralized `runtime/timeline_projection.py` contract from prior work, and the focused timeline projection tests. Confirmed the remaining production gap was exactly the `_timeline_event()` delegation previously identified.

### Changes / actions

- Retried a fresh repository clone before mutation; DNS still fails with `Could not resolve host: github.com`, so no executable checkout was obtained.
- Replaced `runtime/incident_service.py` from its complete exact blob, making only the intended production integration: import `timeline_payload` and delegate `_timeline_event()` payload construction to `timeline_payload(event.event_type, event.payload, _TIMELINE_PAYLOAD_FIELDS)`.
- Verified the repository compare reports exactly 2 additions and 2 deletions in `runtime/incident_service.py`; no unrelated lifecycle code changed.
- Added `runtime/tests/test_audit_timeline_reconciliation_projection.py` exercising the public `IncidentService.audit_timeline()` path. The regressions require canonical reconciliation events to expose only `result`/`reason`, require actor identity to remain fingerprinted, and assert operation IDs, provider bodies, targets, and credential-like values are absent. A contradictory event/payload pair must fail closed to an empty payload.

### Checks / results

- Exact-blob read and GitHub connector writes succeeded.
- Repository diff verification confirmed the lifecycle edit is minimal (2 additions, 2 deletions).
- Direct clone still fails on DNS before checkout, so the new public regressions were not executed and no new green claim is made.
- No GitHub Actions workflow was created or triggered. No credentials, Grafana Cloud, Gemini, Google Cloud resources, remediation provider, or unrelated repository was touched.

### Decisions

1. Public timeline projection now has one centralized disclosure policy rather than separate static and reconciliation paths.
2. Reconciliation audit metadata remains durable internally but operator-visible projection is fail-closed and intentionally lossy.
3. Keep actor disclosure pseudonymous through the existing SHA-256-derived `actor_ref`; never surface raw actor identity in timeline responses.
4. Preserve the no-noisy-CI constraint; validation remains local/focused when an executable checkout becomes available.

### Blockers / unknowns

- The newly integrated public reconciliation timeline tests still require execution in a real checkout.
- Consolidated execution of recent execution-safety/remediation/recovery regressions is still required.
- Historical full-suite failures/errors still need classification from an executable checkout.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- Disposable private Cloud Run acceptance still requires suitable credentials/environment and Docker.

## Single best next step

As soon as an executable checkout is available, run the focused timeline projection/public audit tests plus the execution-safety reconciliation suite and fix any integration/import failure found; if they pass, move to the pinned Grafana MCP 1.4.1 read-only smoke and classify the historical full-suite failures.

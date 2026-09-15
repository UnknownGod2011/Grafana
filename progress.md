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

## Run log — 2026-09-15 — blob-safe timeline integration path

### Inspected at start

Read `progress.md` completely first. Re-read `runtime/incident_service.py` and confirmed `_timeline_event()` still constructs public payloads directly from `_TIMELINE_PAYLOAD_FIELDS`; the centralized `timeline_payload()` integration therefore remains the exact production gap.

### Changes / actions

- Retried a fresh repository clone; DNS still fails with `Could not resolve host: github.com`, so no executable checkout was obtained.
- Identified and validated a safer connector path that was not available in prior runs: fetching the exact `incident_service.py` blob by SHA returns the complete source rather than the truncated whole-file contents response. This removes the previous uncertainty about reconstructing lifecycle-critical source from incomplete connector output.
- Confirmed the current `incident_service.py` blob SHA is `36e59ee38228d761be5a3e3117afa041f9cd202f`, current main head is `b4f76a9977573bb9438b5c9414cb00beb51ae4fe`, and the base tree is `90433d5f57738df2fea38fcb3836e94f7ad4005b`.
- Did not mutate `incident_service.py` in this run because the connector still exposes replacement/Git-data writes rather than a line patch, and the edit must preserve the complete fetched blob exactly except for the import and projector call. The complete blob is now obtainable, so this is no longer blocked on source truncation.

### Checks / results

- Authenticated GitHub repository, ref, commit, and exact blob reads succeeded.
- Direct clone still fails on DNS before checkout.
- No tests were executed and no new green claim is made.
- No GitHub Actions workflow was created or triggered. No credentials, Grafana Cloud, Gemini, Google Cloud resources, remediation provider, or unrelated repository was touched.

### Decisions

1. Use exact-blob retrieval as the source of truth for any connector-based lifecycle-file replacement; never reconstruct a large source file from a truncated contents response.
2. Keep the required production change minimal: import `timeline_payload` and delegate `_timeline_event()` payload construction to `timeline_payload(event.event_type, event.payload, _TIMELINE_PAYLOAD_FIELDS)`.
3. Preserve the no-noisy-CI constraint; validation remains local/focused when an executable checkout becomes available.

### Blockers / unknowns

- `incident_service._timeline_event()` still needs the one-call delegation to `timeline_payload(...)`, followed by a public `audit_timeline()` non-disclosure regression.
- Consolidated execution of recent execution-safety/remediation/recovery regressions is still required.
- Historical full-suite failures/errors still need classification from an executable checkout.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- Disposable private Cloud Run acceptance still requires suitable credentials/environment and Docker.

## Single best next step

Use the complete exact blob as the basis for a minimal connector replacement of `runtime/incident_service.py`, wiring `timeline_payload()` into `_timeline_event()` without altering unrelated lifecycle code; then add the public `audit_timeline()` disclosure/non-disclosure regression and execute it as soon as a local checkout is available.

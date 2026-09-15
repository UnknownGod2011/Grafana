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

## Run log — 2026-09-15 — reconciliation integration edit path revalidated

### Inspected at start

Read `progress.md` completely first. Re-read the relevant import section and `_timeline_event()`/`audit_timeline()` region of `runtime/incident_service.py`, and re-read `runtime/timeline_projection.py`. Retrieved the complete current `incident_service.py` blob through the authenticated GitHub connector to verify that the previously identified integration point has not moved.

### Changes made

No runtime behavior was changed. The intended runtime patch remains exactly two semantic changes: import `reconciliation_timeline_payload` in `incident_service.py`, then use it only as the fallback when `_TIMELINE_PAYLOAD_FIELDS` has no static projection for the event. Existing static projections remain authoritative.

### Checks / results

- Authenticated GitHub connector reads succeeded for the current repository and complete lifecycle-service blob.
- Confirmed `_timeline_event()` still projects unknown event types to an empty payload, so reconciliation result/reason are not yet operator-visible.
- Confirmed `reconciliation_timeline_payload()` remains fail-closed: canonical stage/result/reason must agree between event name and payload, otherwise it returns `{}`.
- Retried a patch-capable local checkout; `git clone` still failed with `Could not resolve host: github.com`.
- No tests were executed and no green claim is made.
- No GitHub Actions workflow was created or triggered. No credentials, Grafana Cloud, Gemini, Google Cloud resources, remediation provider, or unrelated repository was touched.

### Decisions

1. Do not replace the complete lifecycle-critical `incident_service.py` through a whole-file contents write merely to land a two-line patch while the checkout cannot run tests.
2. Do not add a regression that is known to fail until the integration can be landed in the same validated edit path.
3. Treat the checkout DNS failure as transient; preserve the recurring task because useful implementation work resumes as soon as patch-capable repository access is restored.

### Blockers / unknowns

- The reconciliation projector still needs to be wired into `incident_service._timeline_event` and covered through the public `audit_timeline()` path.
- Consolidated execution of recent execution-safety/remediation/recovery regressions is still required.
- Historical full-suite failures/errors still need classification from an executable checkout.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- Disposable private Cloud Run acceptance still requires suitable credentials/environment and Docker.

## Single best next step

As soon as a patch-capable checkout succeeds, land the minimal `incident_service.py` reconciliation projector fallback and its public `audit_timeline()` non-disclosure regression in the same change, run focused timeline tests, then execute the local uncertainty, reconciliation-gate, execution-safety, remediation transport/receiver, and recovery/no-replay suites before further lifecycle changes.

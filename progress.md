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

## Run log — 2026-09-15 — timeline integration tooling discovery

### Inspected at start

Read `progress.md` completely first. Re-inspected `runtime/incident_service.py` and `runtime/timeline_projection.py`. Confirmed `_timeline_event()` still projects only `_TIMELINE_PAYLOAD_FIELDS`, while `reconciliation_timeline_payload()` already provides the intended canonical fail-closed reconciliation projection.

### Changes made

No runtime behavior was changed. I discovered that the GitHub connector's blob reader can retrieve the complete lifecycle-critical `incident_service.py` even though normal file/API reads truncate it. This removes the previous information-access blocker, but the available write primitives still replace an entire blob/file rather than applying a textual patch. I did not manually reconstruct and replace a large lifecycle-critical file from tool output because that remains an unnecessary corruption risk for a two-line integration.

### Checks / results

- Authenticated GitHub connector reads succeeded.
- `runtime/incident_service.py` blob was retrieved completely and the exact integration point was reconfirmed.
- `runtime/timeline_projection.py` was retrieved completely; its canonical reconciliation projector remains intact.
- Fresh `git clone https://github.com/UnknownGod2011/grafana.git` again failed with `Could not resolve host: github.com`.
- No tests were executed and no green claim is made.
- No GitHub Actions workflow was created or triggered. No credentials, Grafana Cloud, Gemini, Google Cloud resources, remediation provider, or unrelated repository was touched.

### Decisions

1. Preserve lifecycle code rather than perform a risky whole-file replacement for a tiny observability integration.
2. Treat complete blob retrieval as useful inspection capability, not as evidence that whole-file mutation is safe.
3. Resume the planned integration immediately when a patch-capable checkout/edit path is available.

### Blockers / unknowns

- `reconciliation_timeline_payload()` still needs to be wired into `incident_service._timeline_event` and covered through the public `audit_timeline()` path.
- Consolidated execution of recent execution-safety/remediation/recovery regressions is still required.
- Historical full-suite failures/errors still need classification from an executable checkout.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- Disposable private Cloud Run acceptance still requires suitable credentials/environment and Docker.

## Single best next step

Retry a patch-capable repository checkout/edit path; when available, import `reconciliation_timeline_payload` in `incident_service.py`, have `_timeline_event()` use it for canonical reconciliation events while retaining the static allowlist for existing events, add a public `audit_timeline()` disclosure/integrity regression, run focused timeline tests, then execute the local uncertainty, reconciliation-gate, execution-safety, remediation transport/receiver, and recovery/no-replay suites before further lifecycle changes.

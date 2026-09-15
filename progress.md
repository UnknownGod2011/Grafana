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

## Run log — 2026-09-15 — integration blocked safely

### Inspected at start

Read `progress.md` completely first. Re-inspected `runtime/incident_service.py` around `_timeline_event()` and `audit_timeline()`, plus `runtime/timeline_projection.py`. Confirmed the remaining integration is exactly as previously recorded: `_timeline_event()` still uses only `_TIMELINE_PAYLOAD_FIELDS`, while `reconciliation_timeline_payload()` contains the canonical fail-closed reconciliation projection logic.

### Changes made

No runtime code was changed in this run. A fresh patch-capable checkout was attempted first so the small integration could be made and tested safely; the runner again failed DNS resolution for `github.com`. I deliberately did not replace the entire large `incident_service.py` through the connector for a two-line import/projection change, because that write primitive requires complete-file replacement and an accidental truncation would be a materially worse production defect than the current bounded observability omission.

### Checks / results

- Authenticated GitHub connector reads succeeded.
- Fresh `git clone https://github.com/UnknownGod2011/grafana.git` failed with `Could not resolve host: github.com`.
- Confirmed `_timeline_event()` still projects static allowlisted payload fields only.
- Confirmed `reconciliation_timeline_payload()` remains present and fail-closed on noncanonical stage/result/reason or event/payload disagreement.
- No tests were executed and no green claim is made.
- No GitHub Actions workflow was created or triggered. No credentials, Grafana Cloud, Gemini, Google Cloud resources, remediation provider, or unrelated repository was touched.

### Decisions

1. Do not trade a bounded operator-observability omission for a high-risk whole-file replacement of lifecycle-critical code.
2. Keep the already-reviewed projector unchanged until it can be integrated through a patch-capable checkout or another minimal-edit mechanism.
3. Do not add unrelated speculative hardening merely to manufacture activity while the highest-value next edit is blocked.

### Blockers / unknowns

- `reconciliation_timeline_payload()` still needs to be wired into `incident_service._timeline_event` and covered through the public `audit_timeline()` path.
- Consolidated execution of recent execution-safety/remediation/recovery regressions is still required.
- Historical full-suite failures/errors still need classification from an executable checkout.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- Disposable private Cloud Run acceptance still requires suitable credentials/environment and Docker.

## Single best next step

Retry a patch-capable repository checkout; when available, wire `reconciliation_timeline_payload()` into `_timeline_event()`, add the public `audit_timeline()` disclosure/integrity regression, run the focused timeline tests, then execute the local uncertainty, reconciliation-gate, execution-safety, remediation transport/receiver, and recovery/no-replay suites before further lifecycle changes.

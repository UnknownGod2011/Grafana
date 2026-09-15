# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the read-only runtime evidence plane. The implemented vertical slice includes deterministic telemetry, Prometheus/Loki/Grafana, official Grafana MCP access, bounded investigation and diagnosis, optional Gemini briefing, exact-revision approval, remediation adapters, telemetry-verified recovery, authenticated lifecycle state, checkpoint/audit integrity, operator UI, Cloud Run deployment hardening, watchdog observability, authenticated private metrics bridging, evidence-unavailable abstention, no-replay execution reconciliation, recovery-only Grafana rechecks, fixed-cardinality recovery observability, stdio-only Grafana MCP launchers, strict operator-API authentication/framing/protocol preflight, and a loopback reference remediation provider with idempotent writes plus read-only operation reconciliation.

Detailed older run history remains in Git history; this file keeps the current invariants, validation baseline, latest run, blockers, and next step.

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
- Reconciliation timeline projection is bounded to validated `result` and `reason` values; operation IDs, provider bodies, targets, credentials, and arbitrary audit metadata must never be exposed.

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected Windows-specific permission test skipped.
- Focused core/API/UI suite from the last executable repository run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating the latest hardening/recovery work.
- Historical official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`; pinned `1.4.1` still requires a live smoke.
- Current committed consolidated tests remain blocked from repository execution in the automation runner; connector commits are not treated as passing tests.

## Run log — 2026-09-15 — bounded reconciliation timeline projection

### Inspected at start

Read `progress.md` completely first. Inspected `runtime/incident_service.py` timeline projection and `runtime/execution_safety.py` reconciliation event construction. Confirmed reconciliation events intentionally contain only bounded `result`/`reason` payloads internally, while the generic timeline projector currently drops those fields because reconciliation event types are dynamic.

### Changes made

1. Added `runtime/timeline_projection.py` with a fail-closed `reconciliation_timeline_payload()` helper.
2. The helper recognizes only `remediation_reconciliation_*` events and exposes only validated current reconciliation results (`accepted`, `not_found`, `unknown`) and reasons (`durable_dispatching`, `legacy_unknown`, `post_dispatch_checkpoint_regression`, `phase_unavailable`).
3. Unknown event types, missing fields, and future/unbounded values project to `{}` rather than becoming an arbitrary-data disclosure channel.
4. Added `runtime/tests/test_timeline_projection.py` covering the complete current result/reason matrix and proving operation IDs, provider bodies, targets, and arbitrary metadata are excluded.
5. The helper is intentionally not yet wired into `incident_service._timeline_event`: the repository cannot be checked out in this runner, and the GitHub connector only provides whole-file replacement for the large service module. I did not risk another incomplete replacement after the prior run's connector truncation incident.

### Checks / results

- Attempted a fresh repository checkout before implementation; `git clone https://github.com/UnknownGod2011/Grafana.git` still failed with `Could not resolve host: github.com`.
- Therefore the new unit test has not been executed and no green claim is made.
- Authenticated GitHub connector reads/writes succeeded.
- No GitHub Actions workflow was created or triggered. No credentials, Grafana Cloud, Gemini, Google Cloud resources, remediation provider, or unrelated repository was touched.

### Decisions

1. Keep reconciliation timeline exposure in a dedicated fail-closed helper rather than teaching the generic allowlist to accept arbitrary dynamic event names.
2. Validate payload values independently of the event-type suffix; the audit event name is not authorization to disclose arbitrary payload data.
3. Do not replace the large `incident_service.py` through a truncated connector response. Integration should be a tiny import/call patch once an executable checkout or safe patch-capable path is available.
4. Continue prioritizing executable suite triage over speculative lifecycle changes.

### Blockers / unknowns

- `reconciliation_timeline_payload()` still needs to be integrated into `incident_service._timeline_event` and covered through the public timeline projection path.
- Consolidated execution of recent execution-safety/remediation/recovery regressions is still required.
- Historical full-suite failures/errors still need classification from an executable checkout.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- Disposable private Cloud Run acceptance still requires suitable credentials/environment and Docker.

## Single best next step

Wire `reconciliation_timeline_payload()` into `incident_service._timeline_event` with a public timeline regression as soon as a safe patch-capable checkout is available; then execute the local uncertainty, reconciliation-gate, execution-safety, remediation transport/receiver, and recovery/no-replay suites before further lifecycle changes.

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

## Run log — 2026-09-15 — timeline integration validation boundary

### Inspected at start

Read `progress.md` completely first. Re-read `runtime/incident_service.py` around `_timeline_event()` and `audit_timeline()`, and re-read the complete centralized `runtime/timeline_projection.py`. Confirmed the production gap is exactly as recorded: public timeline projection still constructs payloads from `_TIMELINE_PAYLOAD_FIELDS` locally, while `timeline_payload()` already contains the intended fail-closed static policy plus canonical reconciliation fallback.

### Changes / actions

- Reconfirmed the minimal production edit required: import `timeline_payload` and replace the two local `_timeline_event()` payload-construction lines with `timeline_payload(event.event_type, event.payload, _TIMELINE_PAYLOAD_FIELDS)`.
- Retried a fresh repository clone specifically to obtain a patch-capable, executable checkout before touching lifecycle-critical code. The clone failed before checkout because the runner still cannot resolve `github.com`.
- Checked the current head commit status through the authenticated GitHub connector. No commit status checks are attached, so there is no existing CI result that can substitute for local validation and no CI workflow was triggered.
- Deliberately made no runtime-code mutation through the connector's whole-file replacement operation: `incident_service.py` is large and the full-file connector response is truncated, so reconstructing/replacing it would create a material corruption risk for a two-line lifecycle edit.

### Checks / results

- Authenticated GitHub connector reads succeeded.
- Direct clone result: `fatal: unable to access 'https://github.com/UnknownGod2011/grafana.git/': Could not resolve host: github.com`.
- Current head has no attached commit-status checks.
- No tests were executed and no new green claim is made.
- No GitHub Actions workflow was created or triggered. No credentials, Grafana Cloud, Gemini, Google Cloud resources, remediation provider, or unrelated repository was touched.

### Decisions

1. Preserve the production lifecycle file rather than perform an unverifiable whole-file reconstruction from truncated connector output.
2. Do not add another helper, speculative test, or duplicate projection layer merely to create activity; the implementation helper and contract coverage already exist and the remaining defect is the public integration itself.
3. Treat DNS failure as a transient execution-environment blocker rather than a project blocker; continue attempting the minimal validated integration on subsequent runs.

### Blockers / unknowns

- `incident_service._timeline_event()` still needs the one-call delegation to `timeline_payload(...)`, followed by a public `audit_timeline()` non-disclosure regression.
- Consolidated execution of recent execution-safety/remediation/recovery regressions is still required.
- Historical full-suite failures/errors still need classification from an executable checkout.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- Disposable private Cloud Run acceptance still requires suitable credentials/environment and Docker.

## Single best next step

As soon as a patch-capable checkout is available, wire `timeline_payload()` into `_timeline_event()`, add the end-to-end public `audit_timeline()` reconciliation disclosure/non-disclosure regression, run that focused suite, and only then continue lifecycle changes.

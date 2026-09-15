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
- Static timeline fields expose only bounded JSON scalars; nested objects/arrays, oversized strings, and non-finite numbers fail closed even when their field name is allowlisted.

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected Windows-specific permission test skipped.
- Focused core/API/UI suite from the last executable repository run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating latest hardening/recovery work.
- Historical official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`; pinned `1.4.1` still requires a live smoke.
- Current committed consolidated tests remain blocked from repository execution in this runner; connector commits are not treated as passing tests.
- The earlier `runtime/timeline_projection.py` revision was independently syntax-compiled and exercised in an isolated local smoke on 2026-09-15. The latest static-value hardening has not yet received repository-level execution.

## Run log — 2026-09-15 — static timeline value hardening

### Inspected at start

Read `progress.md` completely first. Re-read the public reconciliation audit regression, the relevant `incident_service.py` import/projection path, `runtime/timeline_projection.py`, and its focused contract tests. Confirmed `_timeline_event()` delegates to centralized `timeline_payload(...)` and the remaining disclosure gap was value shape: an allowlisted static field could still carry a nested object or pathological scalar if a durable audit record were corrupted or produced by an incompatible writer.

### Changes / actions

- Retried a fresh repository clone first; the execution runner still fails DNS resolution with `Could not resolve host: github.com`.
- Hardened `runtime/timeline_projection.py` so static allowlisted values are restricted to bounded JSON scalars: `None`, booleans, integers, finite floats, and strings up to 512 characters.
- Nested mappings/sequences, oversized strings, NaN, and infinities are omitted from the operator-visible payload even when the key itself is allowlisted.
- Kept canonical remediation reconciliation on its stricter semantic projector; its result/reason behavior is unchanged.
- Added contract regressions covering nested secret-bearing values, oversized strings, NaN, and infinity while preserving ordinary static scalar projection.

### Checks / results

- Fresh repository clone: BLOCKED by transient GitHub DNS failure in the execution runner.
- Repository pytest execution: not available in this runner; no green claim is made for the new commits.
- GitHub connector writes succeeded for the helper and focused tests.
- No GitHub Actions workflow was created or triggered. No credentials, Grafana Cloud, Gemini, Google Cloud resources, remediation provider, or unrelated repository was touched.

### Decisions

1. Treat durable audit payloads as untrusted at the disclosure boundary even for historically trusted event names.
2. Preserve valid scalar lifecycle fields while preventing nested provider/credential data from crossing the operator API via an allowlisted key.
3. Keep the 512-character static string bound deliberately generous for current hashes/revisions/status/action/next-step fields while preventing pathological durable values.
4. Do not use noisy CI merely to compensate for the runner's transient DNS failure.

### Blockers / unknowns

- The new static-value hardening and public `audit_timeline()` reconciliation tests still require execution in a real checkout.
- Historical full-suite failures/errors still need classification from an executable checkout.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- Disposable private Cloud Run acceptance still requires suitable credentials/environment and Docker.

## Single best next step

Retry an executable checkout and run the focused timeline projection/public audit tests plus execution-safety reconciliation suite. Fix any compatibility issue introduced by scalar bounding; if green, immediately run the pinned Grafana MCP 1.4.1 read-only smoke and then classify the historical full-suite failures.

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
- The exact committed `runtime/timeline_projection.py` logic was independently syntax-compiled and exercised in an isolated local smoke on 2026-09-15; canonical reconciliation projection returned only `result`/`reason`. This is not a substitute for repository-level tests.

## Run log — 2026-09-15 — isolated projection validation

### Inspected at start

Read `progress.md` completely first. Re-read `runtime/timeline_projection.py`, `runtime/tests/test_timeline_projection_contract.py`, the public `runtime/tests/test_audit_timeline_reconciliation_projection.py`, and the import section of `runtime/incident_service.py`. Confirmed the public integration remains present and the focused disclosure tests target the intended operator-facing path.

### Changes / actions

- Retried a fresh repository clone before doing anything else; DNS still fails with `Could not resolve host: github.com`.
- Independently reconstructed the exact committed `timeline_projection.py` logic in the local runner, compiled it with Python, and executed a canonical reconciliation projection smoke containing an extra secret field.
- The smoke returned only `result=accepted` and `reason=durable_dispatching`; the extra field was not projected.
- No runtime source was changed because the highest-value remaining work is repository-level validation, not additional unvalidated feature surface.

### Checks / results

- `timeline_projection.py` isolated syntax compile: PASS.
- Canonical reconciliation projection disclosure smoke: PASS.
- Full repository/focused pytest execution remains unavailable because a checkout cannot currently be obtained in this runner.
- No GitHub Actions workflow was created or triggered. No credentials, Grafana Cloud, Gemini, Google Cloud resources, remediation provider, or unrelated repository was touched.

### Decisions

1. Do not treat isolated helper validation as equivalent to repository integration validation.
2. Avoid adding more production surface until the newly wired public timeline path can be exercised together with execution-safety reconciliation tests.
3. Preserve the no-noisy-CI constraint rather than using Actions merely to compensate for transient runner DNS.

### Blockers / unknowns

- Public `audit_timeline()` reconciliation tests and consolidated execution-safety/remediation/recovery regressions still require execution in a real checkout.
- Historical full-suite failures/errors still need classification from an executable checkout.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- Disposable private Cloud Run acceptance still requires suitable credentials/environment and Docker.

## Single best next step

Retry an executable checkout; once available, run the focused timeline projection/public audit tests plus execution-safety reconciliation suite and fix any integration/import failure. If green, immediately move to the pinned Grafana MCP 1.4.1 read-only smoke, then classify the historical full-suite failures.

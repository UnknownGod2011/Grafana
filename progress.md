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
- Static timeline fields expose only bounded JSON scalars; nested objects/arrays, oversized strings, arbitrary-precision integers outside signed 63-bit magnitude, and non-finite numbers fail closed even when their field name is allowlisted.

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected Windows-specific permission test skipped.
- Focused core/API/UI suite from the last executable repository run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating latest hardening/recovery work.
- Historical official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`; pinned `1.4.1` still requires a live smoke.
- Current committed consolidated tests remain blocked from repository execution in this runner; connector commits are not treated as passing tests.
- The earlier `runtime/timeline_projection.py` revision was independently syntax-compiled and exercised in an isolated local smoke on 2026-09-15. The latest scalar/integer hardening has not yet received repository-level execution.

## Run log — 2026-09-15 — bounded timeline integer hardening

### Inspected at start

Read `progress.md` completely first. Re-read `runtime/timeline_projection.py` and `runtime/tests/test_timeline_projection_contract.py`. Confirmed the previous value-shape hardening bounded strings and rejected nested/non-finite values, but still accepted arbitrary-precision Python integers under allowlisted static fields.

### Changes / actions

- Hardened `runtime/timeline_projection.py` so allowlisted integer values must fit within signed 63-bit magnitude (`-(2^63-1)` through `2^63-1`). This prevents corrupted durable audit data from producing pathological arbitrary-precision JSON output while preserving normal lifecycle counters/identifiers represented as integers.
- Added a focused contract regression that preserves boundary integers and drops positive/negative 4096-bit integers.
- Kept boolean handling explicit and unchanged; booleans remain valid JSON scalars and are evaluated before Python's `bool`/`int` subtype relationship.
- No CI workflow, cloud resource, credential, remediation target, or unrelated repository was touched.

### Checks / results

- GitHub connector reads/writes succeeded and the implementation/test commits landed on `main`.
- Repository pytest execution remains unavailable from the connector-only path; no green claim is made for the new regression.
- No GitHub Actions workflow was created or triggered.

### Decisions

1. Treat numeric magnitude as part of the operator disclosure boundary, not merely numeric type.
2. Use a conservative signed 63-bit magnitude compatible with ordinary JSON consumers and well beyond StageGuard's expected timeline numeric fields.
3. Continue failing closed on malformed durable audit values rather than coercing or truncating them.
4. Avoid noisy CI solely to compensate for the runner's checkout limitations.

### Blockers / unknowns

- The latest timeline scalar/integer hardening and public `audit_timeline()` reconciliation tests still require execution in a real checkout.
- Historical full-suite failures/errors still need classification from an executable checkout.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- Disposable private Cloud Run acceptance still requires suitable credentials/environment and Docker.

## Single best next step

Run the focused timeline projection/public audit tests plus execution-safety reconciliation suite in an executable checkout. Fix any compatibility issue introduced by scalar/integer bounding; if green, immediately run the pinned Grafana MCP 1.4.1 read-only smoke and then classify the historical full-suite failures.

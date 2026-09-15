# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the read-only runtime evidence plane. The implemented vertical slice includes deterministic telemetry, Prometheus/Loki/Grafana, official Grafana MCP access, bounded investigation and diagnosis, optional Gemini briefing, exact-revision approval, remediation adapters, telemetry-verified recovery, authenticated lifecycle state, checkpoint/audit integrity, operator UI, Cloud Run deployment hardening, watchdog observability, authenticated private metrics bridging, evidence-unavailable abstention, no-replay execution reconciliation, recovery-only Grafana rechecks, fixed-cardinality recovery observability, stdio-only Grafana MCP launchers, strict operator-API authentication/framing/protocol preflight, and a loopback reference remediation provider with idempotent writes plus read-only operation reconciliation.

Detailed older run history remains in Git history; this file keeps current invariants, validation baseline, latest run, blockers, and next step.

## Core invariants

- Grafana/MCP is read-only evidence access; infrastructure-write credentials remain isolated.
- StageGuard's supported MCP deployment is stdio-only and its compose evidence surface is restricted to `datasource,prometheus,loki` with writes and proxied tools disabled.
- The Grafana MCP release smoke must negotiate the exact configured MCP protocol and return structurally valid, bounded server identity/capabilities before StageGuard trusts its advertised tool surface.
- Gemini is advisory and cannot mutate diagnosis, approval, remediation, or recovery state.
- Required evidence unavailability prevents briefing, approval, and execution from becoming actionable.
- Approval is exact-revision-bound and single-use; provider acceptance never counts as recovery.
- Fresh Grafana telemetry is required to verify recovery.
- `recovery_unverified` can only use the recovery-only verification path and cannot replay provider remediation.
- Any remediation side effect followed by ambiguous checkpoint persistence remains behind the execution-uncertainty barrier, including local/non-reconciling adapters and process restarts during reconciliation.
- Execution uncertainty is resolved only through durable reload/reconciliation and fresh Grafana evidence; `/v1/execute` is never the recovery mechanism.
- Production adapters that support provider reconciliation must additionally resolve their server-owned operation ID before fresh evidence can release uncertainty.
- Durable checkpoint/audit failures fail closed; ambiguous provider execution blocks replay.
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
- An earlier `runtime/timeline_projection.py` revision was independently syntax-compiled and exercised in an isolated local smoke on 2026-09-15. The latest scalar/integer hardening has not yet received repository-level execution.

## Run log — 2026-09-16 — Grafana MCP server-metadata hardening

### Inspected at start

Read `progress.md` completely first. Inspected `runtime/mcp_smoke.py` and `runtime/tests/test_mcp_smoke_contract.py` through the GitHub connector. The prior run correctly added exact MCP protocol negotiation and structural `serverInfo` checks, but accepted unbounded/control-character-bearing server name/version values and later emitted the peer-supplied metadata in release-smoke JSON output.

### Changes / actions

- Added `MAX_SERVER_INFO_FIELD_CHARS = 128` and centralized `_bounded_server_info_field()` validation.
- MCP initialize now fails closed when `serverInfo.name` or `serverInfo.version` is empty, exceeds 128 characters, or contains ASCII control/DEL characters.
- This bounds peer-controlled metadata before it is trusted or printed into release evidence, reducing malformed-peer/log-forging and pathological-output risk.
- Expanded `runtime/tests/test_mcp_smoke_contract.py` with oversized-name/version, newline/control-character, DEL-character, and exact-boundary regressions.
- No CI workflow, cloud resource, credential, remediation target, or unrelated repository was touched.

### Checks / results

- GitHub connector reads and source/test commits succeeded.
- This runner still does not provide a materialized executable repository checkout, so the new tests were not executed and no green pytest claim is made.
- No GitHub Actions workflow was created or triggered.

### Decisions

1. Treat MCP peer identity as untrusted input even in a pinned-container release smoke; validate it before rendering it into operator/release output.
2. Keep server identity validation structural rather than pinning the reported name/version string. The Docker image pin remains the artifact identity control, while bounded metadata avoids coupling to harmless upstream naming changes.
3. Preserve the exact protocol-agreement gate and read-only tool-surface gate added in prior runs.

### Blockers / unknowns

- The latest MCP negotiation/metadata/surface tests, MCP compose contract, timeline scalar/integer hardening, public `audit_timeline()` reconciliation tests, and execution-safety reconciliation suite still require execution in a real checkout.
- Historical full-suite failures/errors still need classification from an executable checkout.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- Disposable private Cloud Run acceptance still requires suitable credentials/environment and Docker.

## Single best next step

Run `runtime/tests/test_mcp_smoke_contract.py`, `runtime/tests/test_observability_image_pins.py`, the focused timeline/public-audit tests, and execution-safety reconciliation suite in an executable checkout. If green, run the pinned Grafana MCP 1.4.1 read-only live smoke, then classify the historical full-suite failures.

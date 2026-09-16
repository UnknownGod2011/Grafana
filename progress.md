# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the read-only runtime evidence plane. The implemented vertical slice includes deterministic telemetry, Prometheus/Loki/Grafana, official Grafana MCP access, bounded investigation and diagnosis, optional Gemini briefing, exact-revision approval, remediation adapters, telemetry-verified recovery, authenticated lifecycle state, checkpoint/audit integrity, operator UI, Cloud Run deployment hardening, watchdog observability, authenticated private metrics bridging, evidence-unavailable abstention, no-replay execution reconciliation, recovery-only Grafana rechecks, stdio-only Grafana MCP launchers, strict operator-API authentication/framing/protocol preflight, and a loopback reference remediation provider with idempotent writes plus read-only operation reconciliation.

Detailed older run history remains in Git history; this file keeps current invariants, validation baseline, latest run, blockers, and next step.

## Core invariants

- Grafana/MCP is read-only evidence access; infrastructure-write credentials remain isolated.
- StageGuard's supported MCP deployment is stdio-only and its compose evidence surface is restricted to `datasource,prometheus,loki` with writes and proxied tools disabled.
- MCP launcher overrides are bounded before subprocess creation: raw command length, argv count, individual argument length, terminal/control characters, Unicode line separators, and bidi formatting controls fail closed outside the supported contract while printable Unicode paths remain valid.
- Direct official `grafana/mcp-grafana` Docker launches, including explicit Docker Hub registry aliases, must opt into stdio; registry qualification cannot bypass the transport boundary.
- The Grafana MCP release smoke must negotiate the exact configured MCP protocol and return structurally valid, bounded server identity/capabilities before StageGuard trusts its advertised tool surface.
- MCP peer-advertised tool names are untrusted input and must be non-empty, bounded, and free of ASCII control/DEL characters before they are stored, compared, or rendered in release evidence/errors.
- MCP peer error/result diagnostics are bounded and control-safe before they are emitted; the release smoke must not dump near-frame-limit peer payloads into logs.
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

## Run log — 2026-09-16 — bounded MCP peer diagnostics

### Inspected at start

Read `progress.md` completely first, inspected the repository tree, then inspected `runtime/mcp_smoke.py` and `runtime/tests/test_mcp_smoke_contract.py`. The stdio frame itself was capped at 1 MiB, but JSON-RPC `error`, malformed `result`, tool-error `content`, and successful query `content` could still be interpolated or printed nearly in full. A malicious or pathological MCP peer could therefore turn an otherwise bounded frame into very large release diagnostics.

### Changes / actions

- Added `_bounded_diagnostic()` with a 2,048-character peer-diagnostic budget and an explicit truncation marker.
- Used `repr()` before bounding so embedded control characters are escaped rather than rendered as forged terminal/log lines.
- Applied bounded rendering to JSON-RPC errors, malformed results, tool `isError` content, and the successful query summary emitted by the release smoke.
- Renamed emitted successful evidence from raw `result` to `result_summary` to make the intentionally bounded semantics explicit.
- Added focused contract tests for control escaping, large-payload truncation, and bounded tool-error diagnostics.
- No CI workflow, cloud resource, credential, remediation target, or unrelated repository was touched.

### Checks / results

- GitHub connector repository inspection and source/test commits succeeded.
- This runner still does not expose a materialized executable checkout through the GitHub connector, so the new tests were not executed and no green pytest claim is made.
- No GitHub Actions workflow was created or triggered as a substitute for local validation.

### Decisions

1. Treat MCP response content as untrusted even after the outer JSON-RPC frame passes its 1 MiB transport bound.
2. Bound diagnostics independently from transport frames because operator logs/release evidence have a much smaller useful size budget.
3. Preserve enough prefix context for debugging while making truncation explicit and deterministic.

### Blockers / unknowns

- Latest MCP smoke diagnostic tests, launcher tests, MCP negotiation/metadata/tool-name/surface tests, MCP compose contract, timeline scalar/integer hardening, public `audit_timeline()` reconciliation tests, and execution-safety reconciliation suite still require execution in a real checkout.
- Historical full-suite failures/errors still need classification from an executable checkout.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- Disposable private Cloud Run acceptance still requires suitable credentials/environment and Docker.

## Single best next step

Run `runtime/tests/test_mcp_smoke_contract.py`, `runtime/tests/test_command_line_bounds.py`, `runtime/tests/test_observability_image_pins.py`, the focused timeline/public-audit tests, and execution-safety reconciliation suite in an executable checkout. If green, run the pinned Grafana MCP 1.4.1 read-only live smoke, then classify the historical full-suite failures.

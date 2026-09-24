# StageGuard Progress

## Current status
StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as its read-only runtime evidence plane. The implemented vertical slice includes deterministic telemetry, Prometheus/Grafana, official Grafana MCP access, bounded investigation/diagnosis, optional Gemini briefing, exact-revision approval, remediation adapters, telemetry-verified recovery, authenticated lifecycle state, checkpoint/audit integrity, operator UI, Cloud Run hardening, watchdog observability, execution reconciliation, and hardened local lifecycle tooling.

## Core invariants
- Grafana/MCP is read-only evidence access; infrastructure-write credentials remain isolated.
- Gemini is advisory and cannot mutate diagnosis, approval, remediation, or recovery state.
- Required evidence unavailability prevents briefing, approval, and execution from becoming actionable.
- Approval is exact-revision-bound and single-use; provider acceptance never counts as recovery.
- Fresh Grafana telemetry is required to verify recovery; ambiguous execution cannot replay remediation.
- MCP release acceptance requires meaningful evidence, exact datasource UID, and a genuine Prometheus vector/matrix sample bound to expected labels on the same sampled series.
- Prometheus timestamps/sample values are finite exact built-in numerics representable as float64; arbitrary-precision structured integers fail closed.
- Evidence traversal is limited to known MCP payload envelopes and exact JSON-like built-ins; extension subclasses are opaque.
- Structured evidence work is bounded by collection cardinality and scalar sizes.
- JSON text evidence is size-gated before whole-string whitespace processing; decoder resource failures, duplicate keys, and NaN/Infinity fail closed.
- JSON-RPC transport frames reject duplicate members and non-standard numeric constants before protocol state is interpreted.
- MCP tool discovery is bounded to 256 tools with exact built-in containers, mandatory evidence tools, and literal `readOnlyHint=true` on every advertised tool.
- The live MCP smoke uses the atomic `validated_read_only_tool_map` trust boundary; structural and evidence-only policy validation cannot be bypassed by consuming a partially validated map.
- Generic MCP `tools/call` result content uses `validated_tool_content` as the live smoke's sole generic result-envelope boundary before datasource or Prometheus domain validation.
- Raw PromQL/evidence/sample payloads must not be emitted by normal release-smoke success output.
- Upstream MCP failure material passes through secret-aware, bounded, display-safe diagnostics before becoming operator-visible.
- Validation claims distinguish historical executable results from connector-authored changes not yet run in a checkout.

## Retained validation baseline
- Local onboarding doctor: 8 passed, 1 expected Windows-specific permission test skipped.
- Focused core/API/UI suite from the last executable repository run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating latest lifecycle/security hardening.
- Historical official Grafana MCP smoke: PASS on `grafana/mcp-grafana:1.3.0`; pinned `1.4.1` still requires live smoke.
- Connector-authored changes since the last executable checkout are not treated as passing tests.

## Recent completed work
- Hardened lifecycle startup/cleanup, Docker timeouts, teardown verification, loopback publishing, and MCP container privileges/resources.
- Pinned Grafana `13.2.1` and official Grafana MCP `1.4.1`; release smoke verifies read-only tools and exact datasource UID.
- Added bounded semantic Prometheus evidence parsing with expected-label binding and strict sample-pair semantics.
- Added secret-aware MCP diagnostics and strict evidence-envelope/resource parsing.
- Hardened JSON-text evidence and MCP JSON-RPC transport decoding against duplicate keys, parser resource failures, and non-standard numeric constants.
- Added focused validation-gate selection for the MCP regression boundary.
- Added bounded MCP `tools/list` validation and wired its atomic read-only policy into the live smoke.
- Added a dedicated bounded generic MCP tool-result envelope validator and focused regressions.
- Wired the generic result validator into live datasource and Prometheus tool-call handling, removing the duplicate permissive traversal.
- Added live-smoke integration regressions proving the wrapper accepts valid evidence, translates structural failures to `McpError`, and enforces generic validation before datasource identity interpretation.

## Latest run — 2026-09-24 — live MCP integration regression coverage

### Inspected at start
Read `progress.md` completely, then inspected `runtime/mcp_smoke.py` and the existing dedicated `runtime/tests/test_mcp_tool_result.py` suite. Confirmed that the bounded generic tool-result validator is wired into the live smoke, but the repository lacked a focused regression that imports and exercises the live smoke wrapper itself.

### Exact changes made
- Added `runtime/tests/test_mcp_smoke_tool_result_integration.py` in commit `b1ac79ea9eb53545bfb83639801bad3d0b236a49`.
- Added a valid exact-built-in result control through `_validated_tool_content`.
- Added a hostile outer-dict-subclass case proving `ToolResultError` is translated to the live smoke's `McpError` surface.
- Added a datasource-path regression proving malformed generic envelopes fail before datasource identity interpretation.
- Added a valid-envelope/wrong-datasource regression proving datasource identity remains a distinct fail-closed domain boundary after generic validation.
- No credentials, cloud resources, remediation targets, unrelated repositories, or GitHub Actions workflows were touched.

### Checks / results
- GitHub accepted the new regression file.
- The test is named `test_mcp_*.py`, so it is intended to be owned by the existing focused Grafana MCP validation gate's MCP test discovery pattern.
- This connector environment still does not provide an executable repository checkout, so the new integration test and focused gate were not executed here; no new green claim is made.
- GitHub Actions were intentionally not triggered solely for connector-authored validation.

### Decisions
1. Test the actual live wrapper, not only the lower-level validator, so future refactors cannot silently bypass exception translation or ordering.
2. Keep generic envelope validation and datasource identity as separate fail-closed boundaries and assert their order explicitly.
3. Do not use CI as a substitute for a local focused validation run when the user requested low-noise GitHub Actions usage.

### Blockers / unknowns
- The focused MCP gate still requires an executable checkout run: `python scripts/run_stageguard_validation.py --gate "Grafana MCP" --keep-going`.
- Grafana `13.2.1` + official MCP `1.4.1` Docker acceptance, Viewer-token bootstrap, sanitized real response capture, and datasource HTTP-method observation remain pending.
- Historical full-suite failures/errors still need classification after the focused MCP boundary is green.

## Single best next step
Run the focused `Grafana MCP` validation gate in an executable checkout and fix any integration regressions it exposes; once green, perform the pinned Grafana `13.2.1` + official MCP `1.4.1` live Docker acceptance and capture a sanitized real `query_prometheus` transport fixture for regression coverage.

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
- JSON-RPC response identity is type-strict: StageGuard's positive integer request IDs cannot be satisfied by booleans, strings, subclasses, or mismatched integers.
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
- Added a dedicated bounded generic MCP tool-result envelope validator and wired it into live datasource and Prometheus handling.
- Added live-smoke integration regressions proving generic validation precedes datasource identity interpretation.
- Added and now wired a strict JSON-RPC response-ID boundary preventing Python boolean/integer equality from aliasing MCP request identity.

## Latest run — 2026-09-24 — live JSON-RPC response identity integration

### Inspected at start
Read `progress.md` completely, then inspected `runtime/mcp_smoke.py` and `runtime/mcp_jsonrpc_identity.py`. Confirmed the helper correctly rejects JSON booleans and other non-exact integer IDs, but the live `StdioClient.request()` still used ordinary Python equality (`message.get("id") != request_id`), leaving `true` able to alias request ID `1`.

### Exact changes made
- Updated `runtime/mcp_smoke.py` in commit `56f6911cecf6c84aab9fd1c54b22c142a4c39107`.
- Imported `ResponseIdentityError` and `assert_integer_response_id` from the dedicated identity module.
- Added `_assert_response_id()` as the live smoke adapter; it invokes the strict helper and translates identity failures into the existing `McpError` operational surface without exposing response material.
- Replaced the live request loop's ordinary Python ID comparison with `_assert_response_id(message.get("id"), request_id, method)`. This is now the sole response-ID match boundary after strict JSON decoding.
- Added `runtime/tests/test_mcp_smoke_response_identity_integration.py` in commit `e9d36008fe1f6726c9c4899bb107a640a3fa8f24`.
- Added integration regressions for exact integer acceptance, boolean/string/mismatched-ID rejection, and preservation of `ResponseIdentityError` as the wrapped cause.
- The new test filename matches the existing `test_*mcp*.py` focused-gate ownership convention.
- No credentials, cloud resources, remediation targets, unrelated repositories, or GitHub Actions workflows were touched.

### Checks / results
- GitHub accepted the runtime update and integration regression file.
- This connector environment does not expose an executable repository checkout, so the new integration regression and focused MCP gate were not executed here; no new green claim is made.
- Source inspection confirms the permissive `message.get("id") != request_id` comparison has been replaced in the live request loop.

### Decisions
1. Keep response identity validation after strict JSON frame decoding and before interpreting `error` or `result`, so an incorrectly identified frame cannot affect request state.
2. Translate only the expected protocol identity failure into `McpError`; programmer-contract failures for an invalid internally generated expected ID remain programming errors rather than being silently normalized.
3. Keep diagnostics free of attacker-controlled response-ID values.
4. Do not trigger CI solely for connector-authored changes, preserving the repository's low-noise Actions policy.

### Blockers / unknowns
- The focused MCP gate still requires an executable checkout run: `python scripts/run_stageguard_validation.py --gate "Grafana MCP" --keep-going`.
- Grafana `13.2.1` + official MCP `1.4.1` Docker acceptance, Viewer-token bootstrap, sanitized real response capture, and datasource HTTP-method observation remain pending.
- Historical full-suite failures/errors still need classification after the focused MCP boundary is green.

## Single best next step
Run the focused `Grafana MCP` validation gate in an executable checkout and fix any failures. Once green, perform pinned Grafana `13.2.1` + official MCP `1.4.1` Docker acceptance and capture a sanitized real `query_prometheus` transport fixture so the hardened parser is validated against the actual current server shape.

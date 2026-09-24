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
- Added live-smoke integration regressions proving generic validation precedes datasource identity interpretation.
- Added a strict JSON-RPC response-ID boundary and regressions preventing Python boolean/integer equality from aliasing MCP request identity; live wiring remains the next change.

## Latest run — 2026-09-24 — strict JSON-RPC response identity boundary

### Inspected at start
Read `progress.md` completely, then inspected `runtime/mcp_smoke.py`, the focused MCP validation-gate definition, and the latest live-wrapper regression. The live stdio client currently compares `message.get("id") != request_id` using ordinary Python equality. Because `True == 1`, a malicious or malformed JSON-RPC response with `"id": true` can be accepted as the response to StageGuard's first integer request even though JSON booleans and numbers are distinct protocol values.

### Exact changes made
- Added `runtime/mcp_jsonrpc_identity.py` in commit `cdfb6228ea076b2708f1e6e7e9e03f737cc2848e`.
- Added `assert_integer_response_id`, which requires both the expected ID and response ID to be exact built-in integers and requires exact value equality; booleans, strings, integer subclasses, and mismatched integers fail closed.
- Added `runtime/tests/test_mcp_jsonrpc_identity.py` in commit `c5e05865f6173f39f6c8d2f752b6128dcd1f23b9` with controls for exact integer acceptance and regressions for `true`/`false`, numeric strings, integer subclasses, mismatches, and invalid expected IDs.
- The new test is named `test_*mcp*.py`, so it belongs to the existing focused `Grafana MCP` validation gate.
- No credentials, cloud resources, remediation targets, unrelated repositories, or GitHub Actions workflows were touched.

### Checks / results
- GitHub accepted both new files.
- This connector environment still does not provide an executable repository checkout, so the new test and focused gate were not executed here; no new green claim is made.
- The new response-ID validator is intentionally not yet claimed as an active runtime control: `runtime/mcp_smoke.py` still uses ordinary equality and must be wired to the helper next.

### Decisions
1. Treat JSON-RPC request identity as type-sensitive rather than relying on Python equality semantics.
2. Keep the helper dependency-free and independently testable before changing the live stdio loop.
3. Fail closed on representation ambiguity; StageGuard itself emits only positive integer request IDs, so accepting string or boolean IDs provides no compatibility benefit.
4. Do not trigger CI solely to validate connector-authored changes, preserving the project's low-noise Actions policy.

### Blockers / unknowns
- `assert_integer_response_id` still needs to replace the live `message.get("id") != request_id` comparison in `runtime/mcp_smoke.py`, with `ResponseIdentityError` translated to `McpError`.
- The focused MCP gate still requires an executable checkout run: `python scripts/run_stageguard_validation.py --gate "Grafana MCP" --keep-going`.
- Grafana `13.2.1` + official MCP `1.4.1` Docker acceptance, Viewer-token bootstrap, sanitized real response capture, and datasource HTTP-method observation remain pending.
- Historical full-suite failures/errors still need classification after the focused MCP boundary is green.

## Single best next step
Wire `assert_integer_response_id()` into `StdioClient.request()` as the sole response-ID match boundary, translate `ResponseIdentityError` to `McpError`, and add a live-client regression proving JSON `true` cannot satisfy request ID `1`; then run the focused `Grafana MCP` gate before pinned live Docker acceptance.

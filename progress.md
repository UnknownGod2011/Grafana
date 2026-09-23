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
- The live MCP smoke now uses the atomic `validated_read_only_tool_map` trust boundary; structural and evidence-only policy validation cannot be bypassed by consuming a partially validated map.
- Standard MCP content blocks are transport envelopes; only actual textual payloads can carry JSON evidence.
- Embedded resources admit evidence only through exact-string `resource.text`; URI-less `resource.data`, blob payloads, and arbitrary resource extensions are non-evidentiary.
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
- Added fail-closed collection/work and scalar-size ceilings for Prometheus evidence.
- Hardened JSON-text evidence and MCP JSON-RPC transport decoding against duplicate keys, parser resource failures, and non-standard numeric constants.
- Added focused validation-gate selection for the MCP regression boundary.
- Added separately testable bounded MCP `tools/list` validation plus strict read-only policy and an atomic `validated_read_only_tool_map` API.
- Wired that atomic API into the live MCP smoke and removed the duplicated local tool mapper/policy implementation.

## Latest run — 2026-09-24 — live MCP tool-surface integration

### Inspected at start
Read `progress.md` completely, then inspected `runtime/mcp_smoke.py`, `runtime/mcp_tool_surface.py`, and the MCP transport tests. Confirmed that the hardened atomic tool-surface validator existed but the live smoke still used duplicated local `_tool_map` and `_assert_read_only_tool_surface` implementations.

### Exact changes made
- Updated `runtime/mcp_smoke.py` in commit `77d6f91d462b66a647c7343ebfc9bdc9002e5772`.
- Imported `ToolSurfaceError` and `validated_read_only_tool_map` from the dedicated tool-surface module.
- Removed the duplicated live `_tool_map` and `_assert_read_only_tool_surface` policy implementations and their duplicated constants.
- Added `_validated_tool_map`, a thin runtime adapter that invokes the atomic structural + read-only policy boundary and translates `ToolSurfaceError` into the smoke runner's `McpError` contract.
- Changed `main()` so `tools/list` crosses that single boundary before datasource or Prometheus tool calls can occur.
- Added `runtime/tests/test_mcp_smoke_tool_surface_integration.py` in commit `631b9f6a0bb460039ab8bdf6090d6f14ab4565e0`, covering acceptance of an expanded read-only surface plus structural and policy failure translation into `McpError`.
- No credentials, cloud resources, remediation targets, unrelated repositories, or GitHub Actions workflows were touched.

### Checks / results
- GitHub accepted the implementation and regression-test commits.
- Static review confirms the live smoke can no longer consume its former weaker duplicated tool map: `tools/list` now goes through `validated_read_only_tool_map` before any tool call is issued.
- The connector runtime does not expose an executable checkout, so the new tests were not executed and no green claim is made.
- Historical validation results above remain historical only.

### Decisions
1. Keep the dedicated `mcp_tool_surface` module as the source of truth and make the smoke runner only adapt its domain error into `McpError`.
2. Preserve support for additional official Grafana MCP tools only when every advertised tool is explicitly read-only.
3. Avoid triggering GitHub Actions merely to validate connector-authored edits; use the focused local validation gate when an executable checkout is available.
4. Treat pinned live Docker acceptance as the next release-confidence milestone rather than adding more speculative parser hardening first.

### Blockers / unknowns
- The focused MCP gate still requires an executable checkout run: `python scripts/run_stageguard_validation.py --gate "Grafana MCP" --keep-going`.
- Grafana `13.2.1` + official MCP `1.4.1` Docker acceptance, Viewer-token bootstrap, sanitized real response capture, and datasource HTTP-method observation remain pending.
- Historical full-suite failures/errors still need classification after the focused MCP boundary is green.

## Single best next step
Run the focused `Grafana MCP` validation gate in an executable checkout and fix any integration regressions it exposes; once green, perform pinned Grafana `13.2.1` + official MCP `1.4.1` live Docker acceptance and capture a sanitized real `query_prometheus` transport fixture.

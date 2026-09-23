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
- Prometheus sample timestamps and numeric sample values must be finite, exact built-in numerics representable as float64; arbitrary-precision structured integers fail closed. Numeric-looking timestamp strings are rejected.
- Evidence traversal is limited to known MCP payload envelopes and exact JSON-like built-ins; extension subclasses are opaque.
- Structured MCP evidence work is bounded by collection cardinality and scalar sizes.
- JSON text evidence is size-gated before whole-string whitespace processing; decoder resource-guard failures, duplicate object keys, and non-standard NaN/Infinity constants fail closed.
- JSON-RPC transport frames are decoded strictly: duplicate object members and Python-only NaN/Infinity constants fail closed before protocol state is interpreted.
- MCP tool discovery is bounded to 256 tools with exact built-in containers; the policy module requires the mandatory evidence tools and literal `readOnlyHint=true` on every advertised tool.
- MCP tool mapping plus evidence-only policy validation is exposed as one atomic trust-boundary operation so callers cannot accidentally consume a merely structurally valid surface.
- Standard MCP content blocks are transport envelopes; only actual textual payloads can carry JSON evidence.
- Embedded resources admit evidence only through exact-string `resource.text`; URI-less `resource.data`, blob payloads, and arbitrary resource extensions are non-evidentiary.
- Raw PromQL/evidence/sample payloads must not be emitted by normal release-smoke success output.
- Upstream MCP failure material must pass through secret-aware, bounded, display-safe diagnostics before becoming operator-visible.
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
- Added explicit fail-closed collection/work and scalar-size ceilings for Prometheus evidence.
- Hardened JSON-text evidence and MCP JSON-RPC transport decoding against duplicate keys, parser resource failures, and non-standard numeric constants.
- Added focused validation-gate selection for the MCP regression boundary.
- Added a separately testable bounded MCP `tools/list` validator and strict read-only policy with exact-container checks, a 256-tool work ceiling, mandatory evidence-tool checks, and literal boolean read-only annotations.
- Added `validated_read_only_tool_map` so structural and policy validation can be invoked atomically; integration into the smoke path remains the immediate next edit.

## Latest run — 2026-09-24 — atomic MCP tool-surface boundary

### Inspected at start
Read `progress.md` completely, then inspected `runtime/mcp_smoke.py` and `runtime/mcp_tool_surface.py`. Confirmed the live smoke still has duplicated `_tool_map` / `_assert_read_only_tool_surface` functions while the hardened module is staged outside the live path.

### Exact changes made
- Updated `runtime/mcp_tool_surface.py` in commit `3493110771444a13d9eab234deea9a305904b234`.
- `bounded_tool_map` now also requires the outer `tools/list` result to be an exact built-in dictionary, closing another structured-container subclass ambiguity.
- Added `validated_read_only_tool_map(result)`, which performs bounded mapping and evidence-only policy validation as one fail-closed operation and only returns the tool map after both checks succeed.
- Added `runtime/tests/test_mcp_tool_surface_atomic.py` in commit `355cc6e45c3bfefa626e0d70863661ced30beace` covering a valid expanded read-only surface, missing mandatory tools, false/non-boolean read-only hints, and hostile outer result-container subclasses.
- No credentials, cloud resources, remediation targets, unrelated repositories, or GitHub Actions workflows were touched.

### Checks / results
- GitHub accepted both implementation/test commits.
- Static review confirms the atomic helper cannot return a partially policy-validated surface and the outer result now follows the same exact-built-in-container rule as nested tool/annotation structures.
- This connector runtime does not expose an executable checkout, so the new tests were not executed and no green claim is made.
- The hardened module is still staged: `runtime/mcp_smoke.py` continues to use its duplicated local functions until that file is integrated.

### Decisions
1. Expose one atomic tool-surface validation API rather than asking each caller to remember structural validation and policy enforcement as separate steps.
2. Apply the exact-built-in rule to the outer `tools/list` result as well as the nested `tools`, tool-entry, and annotation containers.
3. Preserve compatibility with additional official Grafana MCP tools only when they explicitly advertise literal `readOnlyHint=true`.
4. Keep connector-authored tests distinct from executable validation and avoid noisy GitHub Actions runs.

### Blockers / unknowns
- `runtime/mcp_smoke.py` still needs to import and call `validated_read_only_tool_map`, translate `ToolSurfaceError` to `McpError`, and delete both duplicated local policy functions; the connector's whole-file replacement API makes that integration edit higher-risk than the isolated module changes made in this run.
- The focused MCP gate still requires an executable checkout run: `python scripts/run_stageguard_validation.py --gate "Grafana MCP" --keep-going`.
- Grafana `13.2.1` + official MCP `1.4.1` Docker acceptance, Viewer-token bootstrap, sanitized real response capture, and datasource HTTP-method observation remain pending.
- Historical full-suite failures/errors still need classification.

## Single best next step
Integrate `validated_read_only_tool_map` into `runtime/mcp_smoke.py` as the sole tool-discovery trust boundary, translating `ToolSurfaceError` to `McpError` and deleting the duplicated local implementations; then run the focused `Grafana MCP` gate before pinned live Docker acceptance.

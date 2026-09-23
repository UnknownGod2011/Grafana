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
- MCP tool discovery is bounded to 256 tools with exact built-in containers; the staged policy module also requires the mandatory evidence tools and literal `readOnlyHint=true` on every advertised tool.
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
- Added a separately testable bounded MCP `tools/list` validator and read-only policy with exact-container checks, a 256-tool work ceiling, mandatory evidence-tool checks, and strict read-only annotations; integration into the smoke path remains the immediate next change.

## Latest run — 2026-09-24 — MCP read-only policy hardening

### Inspected at start
Read `progress.md` completely, then inspected `runtime/mcp_smoke.py`, `runtime/mcp_tool_surface.py`, and the focused tool-surface regressions. The newly extracted bounded mapper was still staged outside the live smoke path, while the read-only policy remained duplicated in `mcp_smoke.py` and interpreted annotation dictionary subclasses permissively.

### Exact changes made
- Extended `runtime/mcp_tool_surface.py` in commit `d6b7e59b2f426b87f17f898a0378d61c82e6b270` with `REQUIRED_READ_TOOLS` and `assert_read_only_tool_surface`.
- The staged policy requires both `list_datasources` and `query_prometheus`, requires an exact built-in validated tool map, requires exact built-in annotation dictionaries, and accepts `readOnlyHint` only when it is the literal boolean `True`.
- Extended `runtime/tests/test_mcp_tool_surface.py` in commit `c157c18bceacabaf52fb1bb59a25864f020c8d83` with positive required/additional read-tool coverage and negative coverage for missing mandatory tools, write-capable/unannotated tools, hostile annotation-dict subclasses, and truthy non-boolean hints.
- No credentials, cloud resources, remediation targets, unrelated repositories, or GitHub Actions workflows were touched.

### Checks / results
- GitHub accepted both implementation/test commits.
- Static review confirms the policy fails closed on annotation container subclasses and `readOnlyHint=1`, while preserving legitimate additional read-only Grafana tools.
- This connector runtime does not expose an executable checkout, so the new tests were not executed and no green claim is made.
- The module is still intentionally described as staged: `runtime/mcp_smoke.py` continues to use its duplicated local `_tool_map` and `_assert_read_only_tool_surface` until the integration edit is completed.

### Decisions
1. Treat MCP tool annotations as security-relevant protocol data rather than advisory UI metadata because StageGuard relies on the official Grafana MCP as a read-only evidence plane.
2. Require literal boolean `True` instead of truthiness to avoid cross-runtime/type ambiguity.
3. Permit additional tools only when each is explicitly read-only; this keeps future official MCP versions compatible without silently admitting write-capable tools.
4. Keep connector-authored tests distinct from executable validation and avoid noisy GitHub Actions runs.

### Blockers / unknowns
- `bounded_tool_map` and `assert_read_only_tool_surface` still need to replace the duplicated local implementations in `runtime/mcp_smoke.py`; until then the stronger policy is staged, not active.
- The focused MCP gate still requires an executable checkout run: `python scripts/run_stageguard_validation.py --gate "Grafana MCP" --keep-going`.
- Grafana `13.2.1` + official MCP `1.4.1` Docker acceptance, Viewer-token bootstrap, sanitized real response capture, and datasource HTTP-method observation remain pending.
- Historical full-suite failures/errors still need classification.

## Single best next step
Wire both `bounded_tool_map` and `assert_read_only_tool_surface` into `runtime/mcp_smoke.py`, translating `ToolSurfaceError` to `McpError` and deleting both duplicated local policy functions; then run the focused `Grafana MCP` gate before pinned live Docker acceptance.

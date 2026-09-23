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
- Added a separately testable bounded MCP `tools/list` validator with exact-container checks and a 256-tool work ceiling; integration into the smoke path remains the immediate next change.

## Latest run — 2026-09-24 — bounded MCP tool-surface validator

### Inspected at start
Read `progress.md` completely, inspected the repository tree, then inspected `runtime/mcp_smoke.py` and its transport regressions. The transport frame is capped at 1 MiB, but `_tool_map` still iterates every advertised tool and accepts list/dict subclasses. That leaves avoidable attacker-controlled work and extension behavior at the `tools/list` trust boundary.

### Exact changes made
- Added `runtime/mcp_tool_surface.py` in commit `53a5f22bd49408ff6ec8e6b66cdf083640f5789b`.
- Added `MAX_MCP_TOOLS = 256` and `bounded_tool_map`, which rejects oversized tool surfaces before iteration, rejects list/dict subclasses, preserves duplicate-name rejection, and bounds/validates display-safe tool names.
- Added `runtime/tests/test_mcp_tool_surface.py` in commit `0a45b7d849a2bb9005499c6be0c6c974e6b1937a` with at-limit acceptance, over-limit early rejection, duplicate-name, hostile-container-subclass, and unsafe-name coverage.
- No credentials, cloud resources, remediation targets, unrelated repositories, or GitHub Actions workflows were touched.

### Checks / results
- GitHub accepted both commits.
- Static review confirms the new validator rejects a 257-entry surface before inspecting individual entries.
- This connector runtime does not expose an executable checkout, so the new tests were not executed and no green claim is made.
- The validator is intentionally not yet claimed as an active runtime control: `runtime/mcp_smoke.py` still uses its local `_tool_map` until the next integration edit.

### Decisions
1. Bound `tools/list` cardinality independently of the outer 1 MiB frame ceiling; byte bounds and semantic-work bounds protect different resources.
2. Require exact built-in list/dict containers at this trust boundary so extension subclasses cannot introduce surprising iteration/access behavior.
3. Keep the validator in a small module so its boundary behavior is directly testable without spawning Docker/MCP.
4. Do not trigger GitHub Actions merely to compensate for the connector runtime lacking an executable checkout.

### Blockers / unknowns
- `bounded_tool_map` still needs to replace the local `_tool_map` implementation in `runtime/mcp_smoke.py`; until then the new cardinality control is staged, not active.
- The focused MCP gate still requires an executable checkout run: `python scripts/run_stageguard_validation.py --gate "Grafana MCP" --keep-going`.
- Grafana `13.2.1` + official MCP `1.4.1` Docker acceptance, Viewer-token bootstrap, sanitized real response capture, and datasource HTTP-method observation remain pending.
- Historical full-suite failures/errors still need classification.

## Single best next step
Wire `bounded_tool_map` into `runtime/mcp_smoke.py` (translating `ToolSurfaceError` to `McpError`), remove the duplicated local mapping logic, then run the focused `Grafana MCP` gate in an executable checkout before the pinned live Docker acceptance.

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
- Remote Grafana credential bootstrap is explicit-opt-in and HTTPS-only; loopback HTTP remains available for the local fixture.
- Grafana bootstrap targets are strict origins: no embedded credentials, path, query, fragment, malformed port, or non-HTTP(S) scheme; literal IPv4/IPv6 loopback addresses are recognized via the standard IP parser.
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
- Added and wired a strict JSON-RPC response-ID boundary preventing Python boolean/integer equality from aliasing MCP request identity.
- Hardened Grafana Viewer-token bootstrap so remote admin credentials can never be sent over plaintext HTTP or via URL-embedded credentials.
- Tightened bootstrap URL handling to a strict origin boundary and generalized loopback recognition to standards-based IPv4/IPv6 parsing.

## Latest run — 2026-09-24 — strict Grafana bootstrap origin boundary

### Inspected at start
Read `progress.md` completely, then inspected `runtime/bootstrap_grafana.py` and its focused MCP-gate regression. The prior transport hardening correctly required remote HTTPS and explicit opt-in, but the URL validator still accepted path/query/fragment components and recognized only three hard-coded loopback spellings. Because every API path is appended to `STAGEGUARD_GRAFANA_URL`, accepting non-origin URLs is ambiguous and unnecessary at a credential-bearing boundary.

### Exact changes made
- Updated `runtime/bootstrap_grafana.py` in commit `f3d46176e2aaf559c6a58ab60baa3edcad2cadce`.
- Added standards-based `ipaddress.ip_address(...).is_loopback` recognition while preserving the exact `localhost` hostname; this supports equivalent literal loopback spellings without treating hostname lookalikes as local.
- Required the configured Grafana URL to be a strict HTTP(S) origin: no path other than `/`, query, fragment, embedded credentials, malformed port, or port outside 1..65535.
- Forced deferred `urllib.parse` port validation to occur inside the fail-closed validation boundary before any network request or credential construction.
- Expanded `runtime/tests/test_mcp_bootstrap_grafana_target_security.py` in commit `0374f0c42a2359961f544775128d33aa4a73d3dd` with IPv4/IPv6 loopback variants, origin-component rejection, malformed/out-of-range ports, and a localhost-lookalike regression.
- No Actions workflows, cloud resources, tokens, remediation targets, or unrelated repositories were touched.

### Checks / results
- GitHub accepted both implementation and focused regression updates.
- The regression remains inside the existing `Grafana MCP` gate by filename.
- This connector runtime still does not expose an executable repository checkout, so the focused MCP gate was not executed and no new green claim is made.

### Decisions
1. Treat `STAGEGUARD_GRAFANA_URL` as an origin rather than a generic URL because StageGuard appends fixed Grafana API paths to it.
2. Use Python's standard IP parser for literal loopback classification instead of maintaining an incomplete string allowlist.
3. Keep DNS hostnames other than exact `localhost` on the remote path; do not infer loopback from a hostname that could resolve differently later.
4. Keep all target validation before admin credential construction or network access.

### Blockers / unknowns
- The focused MCP gate still requires an executable checkout run: `python scripts/run_stageguard_validation.py --gate "Grafana MCP" --keep-going`.
- Grafana `13.2.1` + official MCP `1.4.1` Docker acceptance, Viewer-token bootstrap, sanitized real response capture, and datasource HTTP-method observation remain pending.
- Historical full-suite failures/errors still need classification after the focused MCP boundary is green.

## Single best next step
Run the focused `Grafana MCP` validation gate in an executable checkout and fix any failures. Once green, perform pinned Grafana `13.2.1` + official MCP `1.4.1` Docker acceptance and capture a sanitized real `query_prometheus` transport fixture so the hardened parser is validated against the actual current server shape.

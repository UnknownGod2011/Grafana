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

## Latest run — 2026-09-24 — remote Grafana bootstrap transport hardening

### Inspected at start
Read `progress.md` completely, then inspected `runtime/mcp_smoke.py`, `runtime/mcp_jsonrpc_identity.py`, `docker-compose.yml`, `scripts/run_stageguard_validation.py`, `README.md`, and `runtime/bootstrap_grafana.py`. The pinned local stack and MCP trust boundaries were coherent. The concrete security gap was in credential bootstrap: `STAGEGUARD_ALLOW_REMOTE_BOOTSTRAP=1` allowed the bootstrapper to send Grafana admin Basic credentials to a remote `http://` origin.

### Exact changes made
- Updated `runtime/bootstrap_grafana.py` in commit `a4830e20912968b7a002cae2f9baf33a146a821c`.
- Added pure `_validate_bootstrap_target()` validation before any network request or credential construction.
- Remote Grafana bootstrap now requires both explicit `STAGEGUARD_ALLOW_REMOTE_BOOTSTRAP=1` opt-in and HTTPS.
- Preserved HTTP support only for `localhost`, `127.0.0.1`, and `::1`, which keeps the credential-free local Docker workflow intact.
- Rejected non-HTTP(S) targets, missing hosts, and URLs with embedded username/password material.
- Added focused regression coverage under `runtime/tests/test_mcp_bootstrap_grafana_target_security.py` in commit `ad9f10fe9f76d4eeadbe1edd523bdfe7da651690`; its name places it in the existing `Grafana MCP` gate.
- Removed the transient duplicate unowned test path in commit `7739e243e8cbdee7e47861f9d312309ee5df7852`.
- No Actions workflows, cloud resources, tokens, remediation targets, or unrelated repositories were touched.

### Checks / results
- GitHub accepted the bootstrap hardening and focused regression file.
- The regression covers loopback HTTP, remote opt-in, remote HTTPS enforcement, embedded credentials, invalid schemes, and missing hosts.
- This connector runtime still does not expose an executable repository checkout, so the focused MCP gate was not executed and no new green claim is made.

### Decisions
1. Treat bootstrap admin credentials as a higher-trust secret than the runtime Viewer token and prohibit plaintext remote transport even when remote bootstrap is explicitly enabled.
2. Keep local Docker onboarding frictionless by allowing loopback HTTP only.
3. Keep target validation pure and dependency-free so it can be regression-tested without opening sockets or loading credentials.
4. Keep the regression inside the existing low-noise MCP gate instead of adding CI/workflow machinery.

### Blockers / unknowns
- The focused MCP gate still requires an executable checkout run: `python scripts/run_stageguard_validation.py --gate "Grafana MCP" --keep-going`.
- Grafana `13.2.1` + official MCP `1.4.1` Docker acceptance, Viewer-token bootstrap, sanitized real response capture, and datasource HTTP-method observation remain pending.
- Historical full-suite failures/errors still need classification after the focused MCP boundary is green.

## Single best next step
Run the focused `Grafana MCP` validation gate in an executable checkout and fix any failures. Once green, perform pinned Grafana `13.2.1` + official MCP `1.4.1` Docker acceptance and capture a sanitized real `query_prometheus` transport fixture so the hardened parser is validated against the actual current server shape.

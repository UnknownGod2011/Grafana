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
- Sanitized live MCP captures can be replayed offline only through the same production tool-surface, tool-result, datasource-identity, and Prometheus semantic validators.
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
- Added an offline sanitized MCP fixture replay validator so a real current-server capture can be regression-tested without retaining credentials or requiring Docker/Grafana on every test run.

## Latest run — 2026-09-24 — sanitized MCP fixture replay path

### Inspected at start
Read `progress.md` completely, then inspected the validation harness, runtime tree, and live `runtime/mcp_smoke.py` path. The principal pending milestone remains live acceptance against pinned Grafana `13.2.1` and official MCP `1.4.1`. Because this connector runtime cannot execute the repository/Docker stack, the most useful unblocked work was to make the eventual sanitized live capture durable and replayable through the exact production evidence validators rather than leaving it as an ad-hoc artifact.

### Exact changes made
- Added `runtime/mcp_fixture_replay.py` in commit `f4d03969d7cfeeca515e112ecbf3584b81f5607f`.
- The replay loader is capped at 1 MiB, requires strict UTF-8 JSON, rejects duplicate members and NaN/Infinity, and accepts exactly five documented fields: `tools_list`, `list_datasources`, `query_prometheus`, `datasource_uid`, and `expected_labels`.
- Replay invokes the production `validated_read_only_tool_map`, `validated_tool_content`, `contains_datasource_uid`, and `assert_expected_prometheus_sample` boundaries; it does not implement a weaker parallel parser.
- The fixture schema intentionally has no place for authorization headers, tokens, process environment, or raw query configuration, reducing the chance that a captured acceptance artifact persists credentials.
- Added `runtime/tests/test_mcp_fixture_replay.py` in commit `fb764f717ff29922e6cbfd8bad457f680b060d02` with valid replay plus fail-closed regressions for write-capable tools, wrong datasource identity, wrong expected series labels, duplicate JSON members, and extra/secret fields.
- The regression is automatically owned by the existing `Grafana MCP` gate through the `test_*mcp*.py` pattern.
- No Actions workflows, cloud resources, credentials, remediation targets, or unrelated repositories were touched.

### Checks / results
- GitHub accepted both new implementation/test files.
- Static inspection confirms the replay path reuses the production MCP validation modules rather than duplicating their semantic logic.
- This connector runtime still does not expose an executable repository checkout, so the new test and focused MCP gate were not executed; no new green claim is made.

### Decisions
1. Make the forthcoming real MCP `1.4.1` capture a sanitized semantic fixture rather than storing raw stdio/session material.
2. Reuse production validators for offline replay so a fixture that passes cannot bypass StageGuard's read-only tool policy or evidence semantics.
3. Reject unknown top-level fixture fields to make accidental persistence of secrets conspicuous and fail closed.
4. Keep the fixture replay dependency-light and local; it should remain useful without Grafana, Docker, Gemini, or cloud credentials.

### Blockers / unknowns
- The focused MCP gate still requires an executable checkout run: `python scripts/run_stageguard_validation.py --gate "Grafana MCP" --keep-going`.
- Grafana `13.2.1` + official MCP `1.4.1` Docker acceptance, Viewer-token bootstrap, sanitized real response capture, and datasource HTTP-method observation remain pending.
- The new replay test is connector-authored and not yet executed.
- Historical full-suite failures/errors still need classification after the focused MCP boundary is green.

## Single best next step
Run the focused `Grafana MCP` validation gate in an executable checkout. Once green, perform the pinned Grafana `13.2.1` + official MCP `1.4.1` Docker smoke, save only the five-field sanitized semantic capture expected by `runtime/mcp_fixture_replay.py`, and replay it locally to lock the actual current server response shape into regression coverage.

# StageGuard Progress

## Current status
StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as its read-only runtime evidence plane. The implemented vertical slice includes deterministic telemetry, Prometheus/Grafana, official Grafana MCP access, bounded investigation/diagnosis, optional Gemini briefing, exact-revision approval, remediation adapters, telemetry-verified recovery, authenticated lifecycle state, checkpoint/audit integrity, operator UI, Cloud Run hardening, watchdog observability, execution reconciliation, and hardened local lifecycle tooling.

## Core invariants
- Grafana/MCP is read-only evidence access; infrastructure-write credentials remain isolated.
- Gemini is advisory and cannot mutate diagnosis, approval, remediation, or recovery state.
- Required evidence unavailability prevents briefing, approval, and execution from becoming actionable.
- Approval is exact-revision-bound and single-use; provider acceptance never counts as recovery.
- Fresh Grafana telemetry is required to verify recovery; ambiguous execution cannot replay remediation.
- MCP acceptance requires meaningful evidence, exact datasource UID, and a genuine Prometheus vector/matrix sample bound to expected labels on the same sampled series.
- Prometheus timestamps/sample values are finite exact built-in numerics representable as float64; arbitrary-precision structured integers fail closed.
- Evidence traversal is limited to known MCP payload envelopes and exact JSON-like built-ins; extension subclasses are opaque.
- Structured evidence work is bounded by collection cardinality and scalar sizes.
- JSON text and JSON-RPC frames reject duplicate members, NaN/Infinity, parser resource failures, and invalid protocol identity before state is interpreted.
- MCP response identity is type-strict; booleans, strings, subclasses, and mismatched integers cannot satisfy integer request IDs.
- MCP tool discovery is bounded to 256 tools with mandatory evidence tools and literal `readOnlyHint=true` on every advertised tool.
- Live tool discovery uses the atomic `validated_read_only_tool_map`; generic tool results use `validated_tool_content` before domain interpretation.
- Raw PromQL/evidence/sample payloads must not be emitted by normal release-smoke success output.
- Upstream MCP failure material passes through secret-aware, bounded, display-safe diagnostics before becoming operator-visible.
- Remote Grafana credential bootstrap is explicit-opt-in and HTTPS-only; loopback HTTP remains available locally. Bootstrap targets are strict origins with no embedded credentials/path/query/fragment.
- Sanitized MCP captures replay offline through the same production tool-surface, tool-result, datasource-identity, and Prometheus semantic validators.
- Fixture expected-label selectors are bounded to 32 entries, valid Prometheus label names, and byte-oriented UTF-8 scalar limits before evidence traversal.
- Fixture file size is enforced on bytes actually read with a one-byte sentinel, not a pre-read filesystem size check.
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
- Hardened JSON-text evidence and MCP JSON-RPC transport decoding against duplicate keys, parser resource failures, non-standard numeric constants, and Python boolean/integer response-ID aliasing.
- Added bounded MCP `tools/list` validation and wired its atomic read-only policy into the live smoke.
- Added a dedicated bounded generic MCP tool-result envelope validator and wired it into live datasource and Prometheus handling.
- Hardened Grafana Viewer-token bootstrap so remote admin credentials cannot be sent over plaintext HTTP or via non-origin/credential-bearing URLs.
- Added an offline sanitized MCP fixture replay validator so a real current-server capture can be regression-tested without retaining credentials or requiring Docker/Grafana on every test run.

## Latest run — 2026-09-24 — bounded fixture file loading

### Inspected at start
Read `progress.md` completely, inspected the runtime tree, `runtime/mcp_fixture_replay.py`, and `runtime/tests/test_mcp_fixture_replay.py`. Live Grafana `13.2.1` + official MCP `1.4.1` acceptance remains the principal pending executable milestone. The replay loader still enforced its 1 MiB limit using `stat()` followed by `read_text()`, leaving a check/use race and allowing the actual read allocation to exceed the accepted bound if the file changed after inspection.

### Exact changes made
- Commit `be442e0eeba94a22ce95c755d2236fe0cef2ab4b` replaces the pre-read `stat()`/unbounded `read_text()` sequence with a binary bounded read of `MAX_FIXTURE_BYTES + 1` bytes.
- The extra sentinel byte makes oversize detection independent of filesystem metadata while keeping memory use bounded; empty and oversized captures fail before UTF-8 decoding or JSON parsing.
- UTF-8 is decoded explicitly with strict error handling after the byte bound succeeds; the existing strict JSON duplicate-member/non-standard-number policy is preserved unchanged.
- Commit `127ff5d2a159fac3189e78d905fc63f458680ce6` adds loader regressions for empty files, files one byte beyond the 1 MiB ceiling, and invalid UTF-8, while retaining all semantic replay tests.
- No Actions workflows, credentials, cloud resources, remediation targets, or unrelated repositories were touched.

### Checks / results
- GitHub accepted both implementation and regression changes.
- Static inspection confirms at most 1 MiB + 1 byte is read before fixture size acceptance and that semantic validation still reuses the production MCP validators.
- This connector runtime does not expose an executable checkout, so the focused MCP gate and new tests were not executed; no new green claim is made.

### Decisions
1. Enforce the fixture resource ceiling on bytes actually consumed rather than mutable filesystem metadata.
2. Keep the loader dependency-free and preserve strict UTF-8/JSON semantics.
3. Do not trigger GitHub Actions merely to compensate for the connector runtime lacking an executable checkout.

### Blockers / unknowns
- The focused MCP gate still requires an executable checkout run: `python scripts/run_stageguard_validation.py --gate "Grafana MCP" --keep-going`.
- Grafana `13.2.1` + official MCP `1.4.1` Docker acceptance, Viewer-token bootstrap, sanitized real response capture, and datasource HTTP-method observation remain pending.
- Connector-authored replay changes are not yet executed.
- Historical full-suite failures/errors still need classification after the focused MCP boundary is green.

## Single best next step
Run the focused `Grafana MCP` validation gate in an executable checkout. Once green, perform the pinned Grafana `13.2.1` + official MCP `1.4.1` Docker smoke, save only the sanitized semantic capture expected by `runtime/mcp_fixture_replay.py`, and replay it locally to lock the actual current server response shape into regression coverage.

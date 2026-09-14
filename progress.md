# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the read-only runtime evidence plane. The implemented vertical slice includes deterministic telemetry, Prometheus/Loki/Grafana, official Grafana MCP access, bounded investigation and diagnosis, optional Gemini briefing, exact-revision approval, remediation adapters, telemetry-verified recovery, authenticated lifecycle state, checkpoint/audit integrity, operator UI, Cloud Run deployment hardening, watchdog observability, authenticated private metrics bridging, evidence-unavailable abstention, no-replay execution reconciliation, recovery-only Grafana rechecks, fixed-cardinality recovery observability, stdio-only Grafana MCP launchers, duplicate authentication-header rejection, strict request framing, and fail-closed mutation protocol preflight.

Detailed older run history remains in Git history; this file keeps the current invariants, validation baseline, latest run, blockers, and next step.

## Core invariants

- Grafana/MCP is read-only evidence access; infrastructure-write credentials remain isolated.
- StageGuard's production Grafana MCP adapters and smoke client are local stdio-only subprocess clients; network MCP transports fail closed.
- Investigation and recovery accept only finite non-boolean numeric metric evidence; malformed samples become unavailable and can never prove diagnosis/recovery.
- Loki corroboration validates bounded evidence envelopes, windows, shapes, scope, and event identity.
- Gemini is advisory and cannot mutate diagnosis, approval, remediation, or recovery state.
- Required evidence unavailability prevents briefing, approval, and execution from becoming actionable.
- Approval is exact-revision-bound and single-use; provider acceptance never counts as recovery.
- Fresh Grafana telemetry is required to verify recovery.
- `recovery_unverified` can only use the recovery-only verification path and cannot replay provider remediation.
- Execution uncertainty is resolved only through durable reload/reconciliation and fresh Grafana evidence; `/v1/execute` is never the recovery mechanism.
- Durable checkpoint/audit failures fail closed; ambiguous provider execution blocks replay.
- Authentication credentials are bounded and duplicate credential-bearing headers fail closed.
- Mutating HTTP requests reject every `Transfer-Encoding` field and duplicate `Content-Length` fields before body reads.
- Only the seven documented exact POST mutation paths are eligible for authentication/body processing; unknown or query-bearing POST routes are rejected before body consumption and the connection is closed.
- Every `Expect` header is rejected with 417 before body processing. `handle_expect_100` is explicitly overridden so a future HTTP/1.1 response-mode change cannot silently enable provisional `100 Continue` behavior.
- Metric/Loki activation remains policy-owned and versioned; callers cannot supply arbitrary Grafana queries or datasource identities through the HTTP API.
- Recovery observability remains fixed-cardinality and provider-detail-free.
- The browser cockpit trusts the authenticated server-produced recovery contract and fails closed on malformed/inconsistent lifecycle state.

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected Windows-specific permission test skipped.
- Focused core/API/UI suite from the last executable repository run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating the latest hardening/recovery work.
- Historical official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`; pinned `1.4.1` still requires a live smoke.
- The identity module plus its focused tests were previously reconstructed from committed content and executed independently: 14/14 passed.
- The request-framing boundary was independently exercised through Python's real `BaseHTTPRequestHandler` parser with raw sockets: duplicate/conflicting CL, duplicate identical CL, TE-only chunked, and CL+TE were rejected before mutation; a normal single-CL JSON request succeeded.
- This run independently exercised the new protocol-preflight behavior with a minimal real `ThreadingHTTPServer`: unknown POST and query-bearing POST returned immediate 404 responses without body bytes, `Expect: 100-continue` returned 417, and forcing the handler to HTTP/1.1 still returned 417 through the explicit `handle_expect_100` override.
- Current committed consolidated tests remain blocked from repository execution because this runner cannot resolve `github.com` for a fresh checkout. Connector commits are not treated as passing tests.

## Run log — 2026-09-15 — mutation protocol preflight hardening

### Inspected at start

Read this `progress.md` completely before selecting work. Inspected `runtime/api.py`, the existing raw request-framing regression, `API.md`, Python standard-library `BaseHTTPRequestHandler.parse_request`, and `handle_expect_100` semantics.

Confirmed two adjacent protocol facts:

1. StageGuard currently emits HTTP/1.0 responses, so the standard library does not normally auto-send `100 Continue` for HTTP/1.1 requests. However, the default `handle_expect_100` would send a provisional 100 response if the handler ever moved to HTTP/1.1 response mode.
2. More importantly, `do_POST` authenticated and called `_read_json` before verifying that the request path was a supported mutation endpoint. Therefore an authenticated or otherwise processable POST to an unknown/query-bearing path with a declared-but-unsent body could occupy a request worker waiting for bytes that StageGuard would ultimately discard.

No unrelated repository, cloud resource, Grafana instance, Gemini endpoint, provider credential, IAM binding, or GitHub Actions workflow was modified or triggered.

### Exact changes made

1. Added the explicit `_POST_PATHS` allowlist containing the seven documented lifecycle mutation routes.
2. Changed `StageGuardHandler.do_POST` to parse and validate the exact route before authentication and before `_read_json`.
3. Unknown paths and query-bearing mutation routes now return bounded 404 JSON immediately, set `close_connection=True`, and never read the declared body.
4. Any `Expect` header now returns bounded HTTP 417 `expectation_failed` before authentication/body processing and closes the connection.
5. Overrode `handle_expect_100` to return the same fail-closed 417 response. This is defense-in-depth for any future change from the current HTTP/1.0 response protocol to HTTP/1.1.
6. Kept dispatch keyed to the already-parsed path and added an internal fail-closed 500 guard if the allowlist and dispatch table ever drift.
7. Added `runtime/tests/test_api_protocol_preflight.py` with real raw TCP requests. It verifies immediate rejection without sending the declared body, query-bearing route rejection, normal-HTTP `Expect` rejection, the HTTP/1.1 `handle_expect_100` path, no lifecycle mutation on rejection, and a normal authenticated control POST.
8. Updated `API.md` to document the exact mutation protocol preflight contract.

Commits:
- `e53b59c36b17fe257085974b12a58b9590d38075` — fail closed before reading unsupported POST bodies
- `148c129bc720c3d78ebe873f35b44b8ef622aa64` — raw HTTP protocol preflight regressions
- `acefa5b84cedf588bbdebc9526f2ac5eabaf0f64` — document mutation protocol preflight

### Checks / results

- Authenticated GitHub connector reads/writes succeeded against `UnknownGod2011/Grafana`.
- Inspected the committed `runtime/api.py` diff after write; only the intended allowlist, `Expect` guard, preflight ordering, parsed-path dispatch, and drift guard changed.
- Fresh repository checkout was attempted and remains blocked by `Could not resolve host: github.com`; therefore the committed test modules could not be executed from the repository and no suite-green claim is made.
- Independently exercised the exact protocol behavior using Python's real `ThreadingHTTPServer`/`BaseHTTPRequestHandler` with raw sockets: unknown route => HTTP/1.0 404, query-bearing route => HTTP/1.0 404, normal handler + `Expect` => HTTP/1.0 417, forced HTTP/1.1 handler + `Expect` => HTTP/1.1 417. These responses arrived without sending the declared 4096-byte body.
- No GitHub Actions run was triggered merely to bypass local DNS.

### Decisions

1. Keep StageGuard's mutation surface exact-path-only; POST query strings are unsupported rather than ignored.
2. Reject all `Expect` headers instead of attempting partial RFC interoperability on a privileged lifecycle API.
3. Route rejection must happen before authentication/body reads because unsupported paths do not need request bodies and should not consume worker capacity waiting for them.
4. Preserve the current HTTP/1.0 response protocol; the `handle_expect_100` override exists only as defense-in-depth against a future protocol-version change.

### Blockers / unknowns

- This runner still cannot resolve `github.com` for a fresh repository checkout, so the committed protocol-preflight regression and consolidated suites cannot execute here.
- Recent audit/checkpoint/recovery/Grafana/MCP/auth/request-framing/protocol-preflight regressions still require consolidated execution.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- The real disposable private Cloud Run acceptance still requires a private StageGuard service, least-privilege invoker identity, and Docker.
- Historical full-suite failures/errors remain untriaged; there is still no full-suite green claim.

## Single best next step

**Stop adding speculative HTTP protocol hardening. As soon as repository checkout is executable, run the focused HTTP/auth/MCP/recovery suites plus the full unittest suite, classify the historical 9 failures / 15 errors into stale-test vs genuine-product defects, and fix the highest-severity genuine defect first. If checkout remains unavailable, inspect the historical failing test/run data through the GitHub connector and begin that triage without triggering new CI.**

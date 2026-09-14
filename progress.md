# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the read-only runtime evidence plane. The implemented vertical slice includes deterministic telemetry, Prometheus/Loki/Grafana, official Grafana MCP access, bounded investigation and diagnosis, optional Gemini briefing, exact-revision approval, remediation adapters, telemetry-verified recovery, authenticated lifecycle state, checkpoint/audit integrity, operator UI, Cloud Run deployment hardening, watchdog observability, authenticated private metrics bridging, evidence-unavailable abstention, no-replay execution reconciliation, recovery-only Grafana rechecks, fixed-cardinality recovery observability, stdio-only Grafana MCP launchers, duplicate authentication-header rejection, strict request framing, fail-closed mutation protocol preflight, and a loopback reference remediation provider with idempotent writes plus read-only operation reconciliation.

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
- Provider reconciliation is read-only, keyed only by the server-owned StageGuard operation ID, and never returns mutation action/production/target detail.
- A provider `not_found` reconciliation result is trusted only when the exact requested lookup URL returns the exact bounded `{operation_id, state:not_found}` contract. Generic/malformed/proxy 404s remain `unknown` and keep execution blocked.
- Authentication credentials are bounded and duplicate credential-bearing headers fail closed on the StageGuard operator API.
- Mutating StageGuard HTTP requests reject every `Transfer-Encoding` field and duplicate `Content-Length` fields before body reads.
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
- The StageGuard API protocol-preflight behavior was independently exercised with a real `ThreadingHTTPServer`: unknown/query-bearing POSTs returned immediate 404 without body bytes and `Expect` returned 417, including the explicit HTTP/1.1 `handle_expect_100` path.
- The loopback remediation-provider reconciliation behavior was previously reconstructed and exercised over real HTTP: unknown operation -> 404/not_found, POST acceptance -> 200, subsequent GET -> 200/accepted, bad reconciliation bearer -> 401, conflicting reuse -> 409, one operation retained. Result: PASS.
- This run independently exercised the new reconciliation-404 parser against real `urllib.error.HTTPError` objects: an exact same-URL 404 carrying `{operation_id, state:not_found}` resolved to `not_found`; empty, malformed, generic error, and oversized 404 bodies remained `unknown`.
- Current committed consolidated tests remain blocked from repository execution because this runner cannot resolve `github.com` for a fresh checkout. Connector commits are not treated as passing tests.

## Run log — 2026-09-15 — authoritative provider not-found reconciliation

### Inspected at start

Read this `progress.md` completely before selecting work. Inspected the repository root and the execution-uncertainty path, including:

- `runtime/execution_safety.py`
- `runtime/incident_service.py`
- `runtime/tests/test_execution_safety.py`
- `runtime/http_remediation_transport.py`
- `runtime/tests/test_http_remediation_transport.py`
- `runtime/tests/test_execution_safety_http_transport.py`
- `runtime/remediation_receiver.py`
- `EXECUTION_UNCERTAINTY.md`

A fresh `git clone --depth 1 https://github.com/UnknownGod2011/Grafana.git` was attempted again and still fails with `Could not resolve host: github.com` in this runner.

### Triage decision

Static lifecycle tracing found a genuine no-replay defect in `HttpRemediationTransport.reconcile()`: every HTTP 404 from the configured reconciliation lookup was converted directly into authoritative `not_found`, without validating the response body or final URL. A reverse proxy, WAF, deployment router, stale path, or custom opener could therefore produce a generic 404 that StageGuard interpreted as provider proof that the deterministic operation did not exist.

That is unsafe during `execution_uncertain`. Provider `not_found` is one of the two states that allows StageGuard to leave the provider-ambiguity barrier and proceed to fresh Grafana investigation. A routing 404 is not evidence about the provider's idempotency registry and must remain ambiguous.

While tracing the end-to-end regression, another concrete issue was found in the tests: `runtime/tests/test_execution_safety_http_transport.py` still patched `urllib.request.urlopen`, but production transport networking had already moved to `_default_urlopen_no_redirect()` backed by `urllib.request.build_opener(...).open()`. Those tests therefore no longer intercepted the production seam and could attempt real network I/O against `.example.test`, likely contributing to the historical full-suite errors.

### Exact changes made

1. Hardened `runtime/http_remediation_transport.py` so HTTP 404 reconciliation is no longer automatically `not_found`.
2. Added one strict parser for reconciliation documents. Both 2xx and 404 paths now require exactly `{operation_id, state}` with an exact operation-id echo and only `accepted|not_found` states.
3. A 404 is accepted as `not_found` only when:
   - the response resolves to the exact requested lookup URL;
   - the bounded response body is valid UTF-8 JSON;
   - the document contains exactly `operation_id` and `state`;
   - `operation_id` exactly matches StageGuard's server-owned deterministic ID;
   - `state` is exactly `not_found`.
4. Generic proxy/router 404s, wrong-operation echoes, malformed/extra fields, an `accepted` body carried on HTTP 404, oversized bodies, and different-final-URL 404s all collapse to `unknown`.
5. Updated `runtime/tests/test_http_remediation_transport.py` to lock the authoritative 404 contract and add malformed/generic/wrong-URL 404 regressions.
6. Reworked `runtime/tests/test_execution_safety_http_transport.py` to use `HttpRemediationTransport`'s supported injected `urlopen` seam through a switchable deterministic opener instead of patching the obsolete global `urllib.request.urlopen` path.
7. Updated the end-to-end execution-safety regression so a contract-valid 404 permits reconciliation while a generic 404 keeps `execution_uncertain`, performs no second remediation POST, and surfaces only the bounded unresolved-state error.

Commits:
- `d8762727de5eea733d59a41e55dd03f181cff335` — fail closed on ambiguous reconciliation 404s
- `52ffe422d94fd3b6c30bea69ca3e1b293339dd93` — test authoritative reconciliation not-found contract
- `e8c4a334fbce2bf203c296a8f24590599e74d4a1` — repair concrete HTTP reconciliation safety tests

### Checks / results

- Authenticated GitHub connector reads/writes succeeded against `UnknownGod2011/Grafana`.
- Fresh repository checkout remains blocked by runner DNS; therefore the committed unittest modules were not executed from a checkout and no repository-suite green claim is made.
- Independently exercised the exact new 404 decision rule using Python's real `urllib.request.Request` and `urllib.error.HTTPError` behavior. The exact same-URL provider contract produced `not_found`; empty, malformed JSON, generic `{error:not_found}`, and oversized 404 bodies produced `unknown`.
- Verified by static inspection that the loopback reference provider already emits the required exact 404 body: `{operation_id, state:not_found}`.
- No GitHub Actions workflow was triggered merely to bypass the transient checkout/DNS problem.
- No external Grafana, Gemini, Google Cloud, remediation provider, credential, or unrelated repository was touched.

### Decisions

1. HTTP status alone is not provider idempotency evidence. `not_found` must be authenticated by the bounded application-level reconciliation contract, not inferred from a router status code.
2. Keep `accepted` on HTTP 200 only. A contradictory HTTP 404 carrying `state: accepted` remains `unknown` rather than trying to interpret provider/proxy behavior.
3. Preserve the existing fail-closed execution-uncertainty state machine: ambiguous reconciliation remains blocked and never replays `/v1/execute` or the provider action.
4. Use the transport's explicit dependency-injection seam for deterministic tests; do not patch implementation details that production networking no longer calls.

### Blockers / unknowns

- This runner still cannot resolve `github.com` for a fresh repository checkout, so the committed transport/execution-safety regressions and consolidated suites cannot execute here.
- Recent audit/checkpoint/recovery/Grafana/MCP/auth/request-framing/protocol-preflight/provider-reconciliation regressions still require consolidated execution.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- The real disposable private Cloud Run acceptance still requires a private StageGuard service, least-privilege invoker identity, and Docker.
- Historical full-suite failures/errors remain incompletely triaged; the stale `urllib.request.urlopen` patch found in this run is one plausible source of errors, but there is still no full-suite green claim.

## Single best next step

**When checkout becomes executable, first run `runtime.tests.test_http_remediation_transport` and `runtime.tests.test_execution_safety_http_transport`, then the reference receiver tests and focused recovery/no-replay suite. If those are green, run the full unittest suite and classify every remaining historical failure/error; fix the highest-severity genuine production defect before adding more hardening. If checkout remains unavailable, continue static full-suite triage through the connector, prioritizing stale test seams and end-to-end lifecycle defects over new speculative protocol work.**

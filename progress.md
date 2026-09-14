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
- This run reconstructed the new loopback remediation-provider reconciliation behavior with the same standard-library server logic and executed a real HTTP smoke: unknown operation -> 404/not_found, POST acceptance -> 200, subsequent GET -> 200/accepted, bad reconciliation bearer -> 401, conflicting reuse -> 409, one operation retained. Result: PASS.
- Current committed consolidated tests remain blocked from repository execution because this runner cannot resolve `github.com` for a fresh checkout. Connector commits are not treated as passing tests.

## Run log — 2026-09-15 — reference provider reconciliation

### Inspected at start

Read this `progress.md` completely before selecting work. Inspected the repository tree and recent commits, confirmed there are currently no GitHub Actions runs to mine for the historical 9-failure/15-error output, and inspected:

- `runtime/http_remediation_transport.py`
- `runtime/production_remediation.py`
- `runtime/execution_safety.py`
- `runtime/tests/test_http_remediation_transport.py`
- `runtime/remediation_receiver.py`
- `runtime/tests/test_remediation_receiver.py`
- `runtime/tests/test_http_remediation_tls_integration.py`
- `README.md`

A fresh `git clone --depth 1 https://github.com/UnknownGod2011/Grafana.git` was also attempted and still fails with `Could not resolve host: github.com` in this runner.

### Triage decision

Static inspection initially flagged the oversized remediation-response `ValueError` as a possible transport defect. Deeper inspection showed that behavior is intentional and safety-critical: after provider dispatch may have occurred, the exception propagates into `ExecutionSafeIncidentService`, which marks the operation `execution_uncertain` and forces provider reconciliation rather than incorrectly recording a definitive rejection. The existing regression explicitly requires that exception. No change was made to this no-replay behavior.

The genuine working-software gap selected instead was the built-in reference remediation provider. It accepted idempotent `POST /v1/recover` requests but had no provider reconciliation endpoint, even though StageGuard's production transport and execution-safety flow require read-only reconciliation after ambiguous dispatch. Its `ThreadingHTTPServer` operation registry also used a non-atomic check-then-store sequence for duplicate operation IDs.

### Exact changes made

1. Added authenticated `GET /v1/operations/<operation_id>` to `runtime/remediation_receiver.py`.
2. The endpoint returns only `{operation_id, state}` for accepted operations and a 404 `not_found` contract for absent operations; action, production, target, credentials, and other provider detail are not returned.
3. Invalid reconciliation operation IDs fail closed with 400 and reconciliation requires the same bearer boundary as remediation writes.
4. Added an `operations_lock` to make the idempotency registry's check-and-store operation atomic under `ThreadingHTTPServer`; conflicting reuse can no longer race through the absent-operation check.
5. Refactored operation-ID validation and bearer checking into narrow helpers shared by write and reconciliation paths.
6. Added receiver regressions for not-found -> accepted reconciliation, reconciliation authentication, absence of mutation detail in reconciliation output, and invalid reconciliation IDs.
7. Updated `README.md` governed-remediation and repository-structure sections to document the loopback reference provider's write + read-only reconciliation contract and its non-production scope.

Commits:
- `3cf7e2d6c2256e50c35b398ff884e53e296bd128` — add reference remediation reconciliation endpoint and atomic registry
- `bb027005caad404f33fe1d23a405463ebe57bba5` — test reference provider reconciliation
- `69f4c79c5c0195b96f97d4bfe5cf4656a8482c66` — document reference provider reconciliation contract

### Checks / results

- Authenticated GitHub connector reads/writes succeeded against `UnknownGod2011/Grafana`.
- Fresh repository checkout remains blocked by runner DNS; therefore the committed unittest module was not executed from a checkout and no repository-suite green claim is made.
- Reconstructed the changed reference-provider behavior locally with Python's real `ThreadingHTTPServer` and `http.client`, then syntax-compiled and exercised it over real loopback HTTP. Assertions passed for missing reconciliation, accepted reconciliation, bad bearer rejection, conflicting idempotency-key reuse, and single-operation retention: `receiver reconciliation smoke: PASS`.
- No GitHub Actions workflow was triggered merely to bypass the transient checkout/DNS problem.
- No external Grafana, Gemini, Google Cloud, remediation provider, credential, or unrelated repository was touched.

### Decisions

1. Preserve oversized/malformed post-dispatch response escalation into execution uncertainty; converting it into an ordinary non-retryable rejection could destroy the no-replay safety guarantee.
2. Provider reconciliation remains GET-only/read-only and uses only StageGuard's stable server-owned operation identity.
3. Keep the reference receiver explicitly loopback-only and non-production; it exists to make the provider contract executable without paid infrastructure or external credentials.
4. Make provider-side idempotency check-and-store atomic because the fixture itself uses a threaded HTTP server and should model correct concurrent provider semantics.

### Blockers / unknowns

- This runner still cannot resolve `github.com` for a fresh repository checkout, so the committed receiver regression and consolidated suites cannot execute here.
- Recent audit/checkpoint/recovery/Grafana/MCP/auth/request-framing/protocol-preflight/provider-reconciliation regressions still require consolidated execution.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- The real disposable private Cloud Run acceptance still requires a private StageGuard service, least-privilege invoker identity, and Docker.
- Historical full-suite failures/errors remain untriaged; there is still no full-suite green claim, and there are no stored GitHub Actions runs containing that historical failure output.

## Single best next step

**When checkout becomes executable, run `runtime.tests.test_remediation_receiver`, the HTTP remediation transport/TLS tests, the focused recovery/no-replay suite, and then the full unittest suite; classify every remaining full-suite failure/error and fix the highest-severity genuine product defect. If checkout is still unavailable, continue static triage through the connector, prioritizing end-to-end provider reconciliation and lifecycle paths over additional speculative protocol hardening.**

# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the read-only runtime evidence plane. The implemented vertical slice includes deterministic telemetry, Prometheus/Loki/Grafana, official Grafana MCP access, bounded investigation and diagnosis, optional Gemini briefing, exact-revision approval, remediation adapters, telemetry-verified recovery, authenticated lifecycle state, checkpoint/audit integrity, operator UI, Cloud Run deployment hardening, watchdog observability, authenticated private metrics bridging, evidence-unavailable abstention, no-replay execution reconciliation, recovery-only Grafana rechecks, fixed-cardinality recovery observability, stdio-only Grafana MCP launchers, strict operator-API authentication/framing/protocol preflight, and a loopback reference remediation provider with idempotent writes plus read-only operation reconciliation.

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
- Provider `not_found` is trusted only when the exact requested lookup URL returns the exact bounded `{operation_id, state:not_found}` contract; generic/malformed/proxy 404s remain `unknown`.
- Operator-API credentials are bounded and duplicate credential-bearing headers fail closed.
- Mutating operator requests reject every `Transfer-Encoding`, duplicate `Content-Length`, unknown/query-bearing mutation routes, and every `Expect` header before body mutation.
- The loopback reference remediation provider now also rejects duplicate `Authorization` and `Idempotency-Key` headers, duplicate/ambiguous `Content-Length`, every `Transfer-Encoding`, and non-JSON media types before touching its idempotency registry.
- Metric/Loki activation remains policy-owned and versioned; callers cannot supply arbitrary Grafana queries or datasource identities through the HTTP API.
- Recovery observability remains fixed-cardinality and provider-detail-free.
- The browser cockpit trusts the authenticated server-produced recovery contract and fails closed on malformed/inconsistent lifecycle state.

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected Windows-specific permission test skipped.
- Focused core/API/UI suite from the last executable repository run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating the latest hardening/recovery work.
- Historical official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`; pinned `1.4.1` still requires a live smoke.
- Identity focused tests were previously reconstructed and executed independently: 14/14 passed.
- Operator request-framing and protocol-preflight boundaries were previously exercised through real `BaseHTTPRequestHandler`/raw-socket paths and behaved fail-closed.
- Reference remediation reconciliation was previously reconstructed and exercised over real loopback HTTP: missing -> 404/not_found, POST -> accepted, GET -> accepted, bad bearer -> 401, conflicting reuse -> 409.
- Authoritative reconciliation-404 parsing was independently exercised with real `urllib.error.HTTPError` objects; only the exact same-URL provider contract resolved to `not_found`.
- Current committed consolidated tests remain blocked from repository execution because this runner cannot resolve `github.com` for a fresh checkout. Connector commits are not treated as passing tests.

## Run log — 2026-09-15 — reference remediation HTTP boundary hardening

### Inspected at start

Read this `progress.md` completely before selecting work. Inspected repository metadata and the current remediation/reconciliation path, including:

- `runtime/http_remediation_transport.py`
- `runtime/production_remediation.py`
- `runtime/remediation_receiver.py`
- `runtime/tests/test_http_remediation_transport.py`
- `runtime/tests/test_remediation_receiver.py`
- repository Actions state (no workflow runs present)

Attempted a fresh shallow checkout and focused remediation tests again. Checkout still fails before test execution with `Could not resolve host: github.com`.

### Triage decision

The reference remediation provider still had a parser-boundary mismatch with the hardened StageGuard operator API. `BaseHTTPRequestHandler` can preserve duplicate headers, but the provider used single-value `.get()` calls for `Authorization`, `Idempotency-Key`, and `Content-Length`, and did not reject `Transfer-Encoding`. That meant an integration/demo provider could accept an ambiguous request whose interpretation may differ across proxies/parsers before mutating its idempotency registry.

Although the receiver is deliberately loopback-only and never touches real infrastructure, it is the executable reference for deployment-specific remediation integrations. Keeping weaker framing/authority semantics there teaches an unsafe provider contract and undermines end-to-end no-replay testing.

### Exact changes made

1. Added a single-header helper in `runtime/remediation_receiver.py`; authentication now requires exactly one `Authorization` header.
2. POST remediation now requires exactly one `Content-Length` and rejects every `Transfer-Encoding` before reading the body.
3. POST remediation now requires exactly one `Idempotency-Key` header before mutation.
4. The provider now requires an `application/json` media type (parameters such as charset remain allowed) before decoding the remediation document.
5. All of these validation failures occur before the idempotency registry is read or written.
6. Extended `runtime/tests/test_remediation_receiver.py` with real raw-socket HTTP regressions for duplicate Authorization, duplicate Idempotency-Key, duplicate Content-Length, Transfer-Encoding, CL+TE ambiguity, and unsupported media type. Every unsafe case asserts that `server.operations` remains empty.
7. Preserved the existing atomic operation-registry lock and the strict read-only reconciliation contract.

Commits:
- `1d17392ef70f8acc728ec80c2d2a1fbc0ab298ea` — harden reference remediation request boundary
- `73612c27ed62c7a76c742ef110de20059e20258c` — test strict remediation receiver headers and framing

### Checks / results

- Authenticated GitHub connector reads/writes succeeded against `UnknownGod2011/Grafana`.
- GitHub Actions currently reports zero workflow runs; no CI was triggered.
- Fresh local checkout remains blocked by DNS (`Could not resolve host: github.com`), so the newly committed raw-HTTP regressions were not executed from a repository checkout and no green claim is made.
- Static cross-check confirms normal `http.client` test requests still send one Authorization, Content-Type, Idempotency-Key and Content-Length, so the existing happy-path contract remains compatible.
- No Grafana Cloud, Gemini, Google Cloud, real remediation provider, credentials, or unrelated repositories were touched.

### Decisions

1. Keep the reference receiver loopback-only, but make its wire contract production-shaped rather than permissive; reference integrations should demonstrate the safe parser boundary.
2. Reject ambiguous framing instead of attempting to normalize it. StageGuard should never rely on a proxy and provider choosing the same interpretation of duplicated framing headers.
3. Require exactly one idempotency header because the provider mutation identity is security-critical and must not be parser-order dependent.
4. Do not add or trigger GitHub Actions merely to compensate for this runner's transient DNS limitation.

### Blockers / unknowns

- This runner still cannot resolve `github.com` for a fresh checkout, so the committed receiver regressions and consolidated suites cannot execute here.
- Recent audit/checkpoint/recovery/Grafana/MCP/auth/framing/provider-reconciliation regressions still require consolidated execution.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- The real disposable private Cloud Run acceptance still requires a private StageGuard service, least-privilege invoker identity, and Docker.
- Historical full-suite failures/errors remain incompletely triaged; there is still no full-suite green claim.

## Single best next step

**When checkout becomes executable, run `runtime.tests.test_remediation_receiver`, `runtime.tests.test_http_remediation_transport`, and `runtime.tests.test_execution_safety_http_transport` first, then the focused recovery/no-replay suite. If green, run the full unittest suite and classify every remaining historical failure/error. If checkout remains unavailable, continue connector-level static triage of existing tests and lifecycle seams rather than adding speculative protocol features.**

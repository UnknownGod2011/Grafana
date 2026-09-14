# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the read-only runtime evidence plane. The implemented vertical slice includes deterministic telemetry, Prometheus/Loki/Grafana, official Grafana MCP access, bounded investigation and diagnosis, optional Gemini briefing, exact-revision approval, remediation adapters, telemetry-verified recovery, authenticated lifecycle state, checkpoint/audit integrity, operator UI, Cloud Run deployment hardening, watchdog observability, authenticated private metrics bridging, evidence-unavailable abstention, fail-closed HTTP/operator handling, no-replay reconciliation for post-remediation persistence uncertainty, versioned metric/Loki onboarding activation, recovery-only Grafana rechecks after accepted remediation, fixed-cardinality recovery observability, stdio-only Grafana MCP launcher enforcement across production and smoke tooling, duplicate authentication-header rejection, and fail-closed HTTP mutation request framing.

Detailed older run history remains in Git history; this file keeps the current invariants, validation baseline, latest run, blockers, and next step.

## Core invariants

- Grafana/MCP is read-only evidence access; infrastructure-write credentials remain isolated.
- StageGuard's production Grafana MCP adapters and smoke/acceptance client are local **stdio-only** subprocess clients. Explicit SSE/streamable-HTTP launchers fail closed, and direct use of the official Docker image requires explicit `-t stdio` before the child process can be spawned.
- Investigation and recovery accept only finite non-boolean numeric metric evidence; malformed samples become unavailable and can never prove diagnosis/recovery.
- Loki corroboration validates adapter envelopes, exact evidence windows, record budgets/shapes, scope, and event identity before corroborating a diagnosis.
- Gemini is advisory and cannot mutate diagnosis, approval, remediation, or recovery state.
- Required evidence unavailability prevents briefing, approval, and execution from becoming actionable.
- Approval is exact-revision-bound and single-use; remediation acceptance requires literal boolean `True`.
- Provider action success never counts as recovery; fresh Grafana telemetry must prove recovery.
- Once an accepted provider action has produced `recovery_unverified`, follow-up verification uses a recovery-only path with no remediation client and therefore cannot replay the provider side effect.
- Durable `recovery_unverified` state survives restart and remains eligible only for recovery-only verification; `recovered` is terminal.
- Durable checkpoint/audit failures fail closed; once provider dispatch may have occurred, persistence uncertainty blocks replay.
- Production remediation HTTP requests never follow redirects and do not redirect bearer/idempotency authority.
- Authentication/identity inputs are bounded and attacker-controlled credentials are bounded before comparison.
- Bearer and Google IAP authentication each require exactly one credential-bearing HTTP header; duplicate `Authorization` or `X-Goog-IAP-JWT-Assertion` fields fail closed before credential comparison or JWT verification.
- Mutating HTTP requests reject every `Transfer-Encoding` field and reject duplicate `Content-Length` fields, including identical duplicates, before reading body bytes or invoking lifecycle mutation logic.
- Metric activation v2 pins the exact ordered eight-query profile contract; Loki activation v2 pins policy-owned LogQL/limit and bounded preflight evidence.
- The reference Grafana MCP dependency is pinned to `grafana/mcp-grafana:1.4.1`; read-only/tool-surface restrictions are regression-locked.
- Core remediation watchdog clocks are finite native numbers; invalid/backward active clocks fail readiness closed.
- Local audit/checkpoint state is symlink/hard-link/path-substitution hardened and owner-private; POSIX checkpoint access is parent-directory-descriptor bound.
- Local checkpoint parents must not be group- or world-writable, including sticky world-writable directories.
- Recovery observability is fixed-cardinality and provider-detail-free.
- Durable recovery outcome and execution phase must agree; mismatch fails readiness closed and has a critical Grafana alert.
- The browser cockpit trusts the authenticated server-produced recovery contract. Missing, malformed, self-inconsistent, or checkpoint-inconsistent recovery data fails closed and disables lifecycle mutations.
- The browser recovery control uses only `POST /v1/recovery/recheck`; the operator UI must never infer a need to invoke `/v1/execute` when recovery is already `recovery_unverified`.
- Execution uncertainty is resolved only by durable checkpoint reload plus server-owned provider reconciliation and fresh Grafana evidence; callers never supply provider operation identity/state.
- Fast local recovery-safety validation executes the real embedded operator-console JavaScript; missing Node is an explicit validation failure rather than a silently skipped browser safety check.

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected platform-specific permission test skipped on Windows.
- Focused core/API/UI suite from the last executable repository run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating the latest hardening/recovery work.
- Historical official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`; pinned `1.4.1` still requires a live smoke.
- Current committed recovery/API/Grafana/operator/MCP transport/request-framing regressions remain blocked from repository execution because this runner cannot resolve `github.com`; authenticated connector reads/writes work, but connector commits are not treated as passing tests.
- The identity module plus its focused unit tests were previously reconstructed locally from the exact committed change content and executed independently: 14/14 identity tests passed.
- The exact new request-framing logic was independently exercised against Python's real `BaseHTTPRequestHandler`/`HTTPMessage` parser with raw sockets: duplicate conflicting CL, duplicate identical CL, TE-only chunked, and CL+TE were all rejected with 400 before mutation; the single-CL JSON control request succeeded. This validates parser semantics but is not a claim that the committed repository test module executed.

## Run log — 2026-09-14 — HTTP request-framing hardening

### Inspected at start

Read this `progress.md` completely before selecting work. Inspected the current `runtime/api.py`, `runtime/tests/test_api.py`, test tree, and `API.md`. The previous run explicitly identified HTTP request framing as the next production boundary.

Confirmed a concrete defect in `_read_json`: it used a single-value `headers.get("Content-Length")` lookup and did not inspect `Transfer-Encoding`. Python's request parser preserves repeated fields, so duplicate `Content-Length` values could be interpreted by StageGuard using only one field. A `Transfer-Encoding: chunked` request with no Content-Length was treated as an empty JSON body, which could let an authenticated empty-body lifecycle endpoint execute while transfer-coded bytes remained unread. This is an origin/proxy parser-differential and request-smuggling class boundary and must fail closed.

No unrelated repository, cloud resource, Grafana instance, Gemini endpoint, remediation provider, IAM binding, or GitHub Actions workflow was modified or triggered.

### Exact changes made

1. Added `_header_values` to `runtime/api.py` so security-sensitive framing checks observe every received field-value through `HTTPMessage.get_all`, with a compatibility fallback for simpler header mappings.
2. Changed `_read_json` to reject any `Transfer-Encoding` header before reading body bytes. StageGuard does not implement request transfer coding, so there is no safe reason to accept it.
3. Changed `_read_json` to require at most one `Content-Length` field. Both conflicting and identical duplicates are rejected rather than normalized, eliminating ambiguity across proxies/parsers.
4. Preserved the existing 16 KiB body cap, JSON object requirement, content-type check for non-empty bodies, and empty-body behavior for endpoints whose contract is `{}`.
5. Added `runtime/tests/test_api_request_framing.py`, using real raw TCP/HTTP requests against `make_server` rather than mocked header maps. The regressions cover conflicting duplicate CL, identical duplicate CL, TE-only chunked framing, CL+TE framing, and a normal single-CL control request. Every rejection asserts that no audit event or incident mutation occurred.
6. Updated `API.md` to make the strict mutation request-framing contract explicit for operators and integrators.

Commits:
- `c469599262430c4bef701e4ed76c1cce4eb74a9a` — Harden HTTP request framing before JSON reads
- `ebcd95ebabf2467757397faebd21d94dfa2c0a60` — Add raw HTTP request framing regressions
- `a5effda51c240f01a7734d11b1fb17662221593d` — Document fail-closed HTTP request framing

### Checks / results

- Authenticated GitHub connector read/write operations succeeded against `UnknownGod2011/Grafana`.
- Attempted the intended focused repository execution with `python -m unittest -v tests.test_api tests.test_api_request_framing` from a fresh clone. Checkout still fails first with `Could not resolve host: github.com`; therefore no committed-suite green claim is made.
- Independently reproduced the exact framing helper logic in a minimal Python `ThreadingHTTPServer` and exercised raw requests through the real standard-library HTTP parser. Results: four unsafe framing cases returned HTTP 400 with the intended bounded details; one normal single-CL JSON request returned HTTP 200; the mutation counter incremented only for the normal request.
- No GitHub Actions workflow was triggered merely to bypass the runner DNS failure.

### Decisions

1. Reject all request `Transfer-Encoding` rather than attempting chunked decoding in StageGuard's deliberately minimal origin server.
2. Reject duplicate `Content-Length` even when values are identical. Intermediary normalization differences are unnecessary risk on privileged lifecycle endpoints.
3. Perform framing validation after authentication but before consuming the request body or invoking any incident-service mutation.
4. Keep this change scoped to request framing; do not alter reverse-proxy deployment assumptions or add speculative protocol features.

### Blockers / unknowns

- This runner still cannot resolve `github.com` for a fresh repository checkout, so the committed raw-HTTP regression and consolidated suites cannot execute here.
- Recent audit/checkpoint/retention/recovery/Grafana/MCP/request-framing regressions still require consolidated execution.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- The real disposable private Cloud Run acceptance still requires a private StageGuard service, least-privilege ADC invoker identity, and Docker.
- Historical full-suite failures/errors remain untriaged; there is still no full-suite green claim.

## Single best next step

**Inspect the adjacent HTTP protocol boundary for unsupported `Expect: 100-continue` and method/path handling before body consumption. If the standard-library handler can emit a provisional 100 response or retain ambiguous unread bodies on rejected mutation requests, harden that behavior with raw-socket regressions; otherwise stop protocol hardening and return to the highest-severity historical full-suite defect once checkout is executable.**

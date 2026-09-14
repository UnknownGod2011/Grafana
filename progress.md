# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the read-only runtime evidence plane. The implemented vertical slice includes deterministic telemetry, Prometheus/Loki/Grafana, official Grafana MCP access, bounded investigation and diagnosis, optional Gemini briefing, exact-revision approval, remediation adapters, telemetry-verified recovery, authenticated lifecycle state, checkpoint/audit integrity, operator UI, Cloud Run deployment hardening, watchdog observability, authenticated private metrics bridging, evidence-unavailable abstention, fail-closed HTTP/operator handling, no-replay reconciliation for post-remediation persistence uncertainty, versioned metric/Loki onboarding activation, recovery-only Grafana rechecks after accepted remediation, fixed-cardinality recovery observability, stdio-only Grafana MCP launcher enforcement across both production adapters and smoke/acceptance tooling, and duplicate authentication-header rejection for bearer and Google IAP identity.

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
- Current committed recovery/API/Grafana/operator/MCP transport regressions remain blocked from repository execution because this runner cannot resolve `github.com`; authenticated connector reads/writes work, but connector commits are not treated as passing tests.
- The current identity module plus its focused unit tests were reconstructed locally from the exact committed change content and executed independently: 14/14 identity tests passed.

## Run log — 2026-09-14 — duplicate authentication-header hardening

### Inspected at start

Read this `progress.md` completely before selecting work. Inspected the current repository metadata/tree and the relevant production security surfaces: `runtime/api.py`, `runtime/identity.py`, `runtime/bootstrap.py`, `runtime/http_remediation_transport.py`, `runtime/production_remediation.py`, `runtime/anchored_execution_safety.py`, `runtime/gemini_commander.py`, and `runtime/tests/test_identity.py`.

The previous run had completed the Grafana MCP smoke/acceptance stdio transport boundary. The next useful production issue found was at the HTTP authentication boundary: `StaticBearerIdentityProvider` and `GoogleIapIdentityProvider` each used a single-value header lookup. Python's `BaseHTTPRequestHandler` preserves repeated fields, while proxies and application servers can differ in first/last/combined duplicate-header behavior. Authentication therefore should not depend on which duplicate credential field a parser returns.

No unrelated repository, cloud resource, Grafana instance, Gemini endpoint, remediation provider, IAM binding, or GitHub Actions workflow was modified or triggered.

### Exact changes made

1. Added a small `_header_values` helper in `runtime/identity.py` that reads every occurrence of an authentication header through `HTTPMessage.get_all`, with a defensive compatibility path for simple custom/test handler implementations.
2. Changed static bearer authentication to require exactly one `Authorization` header. Missing credentials retain the existing `bearer authentication required` behavior; duplicates fail closed as `invalid bearer credential` before token comparison.
3. Changed Google IAP authentication to require exactly one `X-Goog-IAP-JWT-Assertion` header. Missing assertions retain the existing required-auth behavior; duplicates fail closed as `invalid IAP assertion` before any verifier call.
4. Preserved existing bounded public authentication-error vocabulary, token length limits, constant-time bearer comparison, signed-IAP claim verification, and the rule that unsigned Google convenience identity headers are never authentication authority.
5. Extended `runtime/tests/test_identity.py` with duplicate-header fixtures and regressions proving bearer duplicates are rejected and duplicate IAP assertions never reach the JWT verifier.

Commits:
- `de5ca42944f89429017e09c9177b3ac0388a5da4` — Reject duplicate authentication credential headers
- `275effdb21e52715f82e2115951a06f0e6017450` — Test duplicate auth-header rejection

### Checks / results

- Authenticated GitHub connector read/write operations succeeded against `UnknownGod2011/Grafana`.
- Reconstructed the updated `runtime/identity.py` and focused `runtime/tests/test_identity.py` locally and ran `python -m unittest -v test_identity.py`.
- Result: **14 tests passed, 0 failures, 0 errors**. The two new duplicate-header cases passed along with the existing identity normalization, bearer-token, IAP verification, error-redaction, and input-boundary tests.
- Fetched the committed `runtime/identity.py` back from `main` after the write and verified the shared `get_all`-based duplicate-header logic is present.
- Attempted a fresh repository checkout before the change; it still failed before tests with `Could not resolve host: github.com`.
- Therefore this run does **not** claim the repository-wide or historical full suite green.
- No GitHub Actions workflow was triggered merely to bypass the runner DNS failure.

### Decisions

1. Treat duplicate credential headers as authentication ambiguity and fail closed rather than relying on parser/proxy first-vs-last behavior.
2. Reuse existing bounded public auth errors instead of introducing attacker-influenced error detail.
3. Keep local-development identity unchanged because it deliberately ignores all request headers and is loopback-gated by bootstrap.
4. Keep the change narrowly scoped to authentication; do not expand into unrelated proxy-header trust or network policy without evidence of a concrete defect.

### Blockers / unknowns

- This runner still cannot resolve `github.com` for a fresh repository checkout, so the consolidated committed suites cannot currently execute here.
- Recent audit/checkpoint/retention/recovery/Grafana/MCP regressions still require consolidated execution.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- The real disposable private Cloud Run acceptance still requires a private StageGuard service, least-privilege ADC invoker identity, and Docker.
- Historical full-suite failures/errors remain untriaged; there is still no full-suite green claim.

## Single best next step

**Inspect and harden the HTTP request-framing boundary next: verify that mutating endpoints reject ambiguous request framing such as conflicting/duplicate `Content-Length` and unsupported `Transfer-Encoding` before reading a JSON body, add focused raw-HTTP regressions, and only then return to historical full-suite triage once a full checkout is executable.**

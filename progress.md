# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the read-only runtime evidence plane. The implemented vertical slice includes deterministic telemetry, Prometheus/Loki/Grafana, official Grafana MCP access, bounded investigation and diagnosis, optional Gemini briefing, exact-revision approval, remediation adapters, telemetry-verified recovery, authenticated lifecycle state, checkpoint/audit integrity, operator UI, Cloud Run deployment hardening, watchdog observability, authenticated private metrics bridging, evidence-unavailable abstention, fail-closed HTTP/operator handling, no-replay reconciliation for post-remediation persistence uncertainty, versioned metric/Loki onboarding activation, recovery-only Grafana rechecks after accepted remediation, a fixed-cardinality recovery lifecycle contract shared by lifecycle JSON/readiness/Prometheus/Grafana, and a browser cockpit that consumes that server-derived recovery contract.

Detailed older run history remains in Git history; this file keeps the current invariants, validation baseline, latest run, blockers, and next step.

## Core invariants

- Grafana/MCP is read-only evidence access; infrastructure-write credentials remain isolated.
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
- Metric activation v2 pins the exact ordered eight-query profile contract; Loki activation v2 pins policy-owned LogQL/limit and bounded preflight evidence.
- The reference Grafana MCP dependency is pinned to `grafana/mcp-grafana:1.4.1`; read-only/tool-surface restrictions are regression-locked.
- Core remediation watchdog clocks are finite native numbers; invalid/backward active clocks fail readiness closed.
- Local audit/checkpoint state is symlink/hard-link/path-substitution hardened and owner-private; POSIX checkpoint access is parent-directory-descriptor bound.
- Local checkpoint parents must not be group- or world-writable, including sticky world-writable directories.
- Recovery observability is fixed-cardinality and provider-detail-free.
- Durable recovery outcome and execution phase must agree; mismatch fails readiness closed and has a critical Grafana alert.
- The browser cockpit trusts the authenticated server-produced recovery contract. Missing, malformed, self-inconsistent, or checkpoint-inconsistent recovery data fails closed and disables lifecycle mutations.
- The browser recovery control must use only `POST /v1/recovery/recheck`; the operator UI must never infer a need to invoke `/v1/execute` when recovery is already `recovery_unverified`.

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected platform-specific permission test skipped on Windows.
- Focused core/API/UI suite from the last executable repository run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating the latest hardening/recovery work.
- Historical official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`; pinned `1.4.1` still requires a live smoke.
- Current committed recovery/API/Grafana/operator regressions remain blocked from repository execution because this automation runner cannot resolve `github.com`; authenticated connector reads/writes work, but commits are not treated as passing tests.

## Run log — 2026-09-14 — behavioral recovery-only request-path lock

### Inspected at start

Read this `progress.md` completely before selecting work. Inspected the existing dependency-free DOM harness in `runtime/tests/test_operator_console_dom.py` and the actual embedded `CONSOLE_JS` in `runtime/operator_console.py`. Confirmed the previous harness proved button/interlock state but did not click the real recovery control or record the resulting request path.

No unrelated repository, cloud resource, Grafana instance, Gemini endpoint, remediation provider, IAM binding, or GitHub Actions workflow was modified or triggered.

### Exact changes made

1. Added `runtime/tests/test_operator_console_dom_requests.py` as a dependency-free behavioral network-path harness for the real `CONSOLE_HTML` and `CONSOLE_JS` assets.
2. The harness runs the actual cockpit JavaScript with Node's built-in `vm` module and creates its DOM from the IDs in the real HTML; it requires no npm package, browser binary, Grafana, Gemini, remediation credentials, or paid service.
3. It injects a valid authenticated cold-restored `recovery_unverified` lifecycle where remediation has already been accepted and the provider execution button must remain disabled.
4. It records every `fetch` request made by the real cockpit, clicks the real `recheck-recovery` control, and returns a server-derived `recovered` lifecycle response.
5. The regression requires exactly one non-GET mutation and pins it to `POST /v1/recovery/recheck` with JSON `{}`, `credentials: same-origin`, and `Content-Type: application/json`.
6. The regression explicitly fails if any request targets `/v1/execute`, behaviorally locking the no-provider-replay browser contract rather than checking source strings.
7. After the mocked recovery response, the regression requires recheck and execute to be disabled, the judge recovery text to become `Verified by Grafana`, and the rendered bounded recovery object to show `state: recovered` and `verified: true`.

Commit:
- `95eca71bcfd101d60488b5cad73bad2b1d5196d9` — Test operator recovery recheck request path

### Checks / results

- Authenticated GitHub connector read/write operations succeeded against `UnknownGod2011/Grafana`.
- Re-read the committed test file from `main` after creation and confirmed the intended request recorder, endpoint assertions, no-`/v1/execute` assertion, and terminal recovered assertions are present.
- Attempted a fresh shallow checkout and focused execution with:
  - `git clone --depth 1 https://github.com/UnknownGod2011/Grafana.git`
  - `python -m unittest tests.test_operator_console_dom tests.test_operator_console_dom_requests -v`
- Checkout failed before any test could run with `Could not resolve host: github.com`.
- Therefore this run does **not** claim either DOM harness green.
- No GitHub Actions workflow was triggered merely to bypass the runner DNS failure.

### Decisions

1. The no-replay property is now tested at the browser request boundary in addition to server/service lifecycle tests: a valid recovery recheck must never transit through `/v1/execute`.
2. The request-path harness remains dependency-free so it can be part of a fast local safety suite without Playwright/jsdom/browser-download churn.
3. Same-origin credentials and JSON request shape are pinned because recovery verification is an authenticated lifecycle mutation and should not silently drift to a different browser authority model.
4. The test uses a server-produced terminal recovery response; the browser is required to render that state rather than infer success from the request completing.

### Blockers / unknowns

- Both DOM harnesses require execution from a current repository checkout; this runner still cannot resolve `github.com`.
- Recent audit/checkpoint/retention/recovery/Grafana regressions still require consolidated execution.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- The real disposable private Cloud Run acceptance still requires a private StageGuard service, least-privilege ADC invoker identity, and Docker.
- Historical full-suite failures/errors remain untriaged; there is still no full-suite green claim.

## Single best next step

**Once executable checkout is available, run `runtime/tests/test_operator_console_dom.py` and `runtime/tests/test_operator_console_dom_requests.py` first and fix any harness/runtime issues. If green, add both to the existing focused local safety test command/documentation, then move to the highest-impact remaining production gap rather than adding more source-only UI assertions.**

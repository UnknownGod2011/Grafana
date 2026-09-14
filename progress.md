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

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected platform-specific permission test skipped on Windows.
- Focused core/API/UI suite from the last executable repository run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating the latest hardening/recovery work.
- Historical official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`; pinned `1.4.1` still requires a live smoke.
- Current committed recovery/API/Grafana/operator regressions remain blocked from repository execution because this automation runner cannot resolve `github.com`; authenticated connector reads/writes work, but commits are not treated as passing tests.

## Run log — 2026-09-14 — executable operator DOM recovery harness

### Inspected at start

Read this `progress.md` completely before selecting work. Inspected `runtime/operator_console.py`, `runtime/tests/test_operator_recovery_recheck.py`, and `runtime/tests/test_api_recovery_recheck.py`. Confirmed the remaining gap was behavioral validation of the actual embedded cockpit JavaScript: existing recovery UI coverage largely asserted source strings rather than executing the DOM/button interlocks.

No unrelated repository, cloud resource, Grafana instance, Gemini endpoint, remediation provider, IAM binding, or GitHub Actions workflow was modified or triggered.

### Exact changes made

1. Added `runtime/tests/test_operator_console_dom.py` as a dependency-free behavioral harness for the real `CONSOLE_HTML` and `CONSOLE_JS` assets.
2. The Python test launches the system `node` executable when available and skips cleanly when Node is absent; it adds no npm package, browser binary, paid service, or network dependency.
3. The harness creates a minimal in-memory DOM from the actual IDs present in `CONSOLE_HTML`, implements the DOM methods used by the cockpit, injects a same-origin mocked lifecycle response, and executes the actual embedded JavaScript through Node's built-in `vm` module.
4. Added behavioral regression coverage proving a valid cold-restored `recovery_unverified` contract enables only the no-provider-replay recovery recheck, keeps provider execution disabled, renders `RECHECK ONLY`, and exposes only the bounded recovery view.
5. Added behavioral regression coverage proving `recovered` is terminal: recheck and provider execution stay disabled and the UI renders `RECOVERED ✓` with verified recovery state.
6. Added behavioral regression coverage proving a malformed recovery contract fails closed: investigation, briefing, approval, execution, and recovery recheck controls are disabled and the lifecycle safety panel is shown.
7. Added behavioral regression coverage proving `checkpoint_phase_consistent=false` keeps remediation/recheck blocked and surfaces lifecycle safety.
8. The harness intentionally uses representative authenticated lifecycle payloads and no Grafana/Gemini/remediation credentials, so it can run as a fast local safety test once a checkout is available.

Commit:
- `07d58b3d50f1cb2baa99132f623e0872363061e1` — Add executable operator console DOM recovery harness

### Checks / results

- Authenticated GitHub connector read/write operations succeeded against `UnknownGod2011/Grafana`.
- A fresh shallow checkout plus focused test execution was attempted with:
  - `git clone --depth 1 https://github.com/UnknownGod2011/Grafana.git`
  - `python -m unittest tests.test_operator_console_dom -v`
- Checkout failed before any test could run with `Could not resolve host: github.com`.
- Therefore this run does **not** claim the new DOM harness green.
- No GitHub Actions workflow was triggered merely to bypass the runner DNS failure.

### Decisions

1. Behavioral UI safety tests should execute the real embedded cockpit script rather than duplicate recovery logic in a test-only implementation.
2. The harness stays dependency-free to avoid npm/browser installation cost and noisy CI churn; Node's standard runtime plus a deliberately small DOM shim is sufficient for the current button/interlock contract.
3. Missing Node is a local-environment skip, not a product failure; environments that ship Node can exercise the JavaScript behavior directly.
4. Recovery tests continue to treat the server recovery object as authoritative and never infer recheck eligibility from nested provider outcome fields.

### Blockers / unknowns

- The new DOM harness requires execution from a current repository checkout; this runner still cannot resolve `github.com`.
- Recent audit/checkpoint/retention/recovery/Grafana regressions still require consolidated execution.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- The real disposable private Cloud Run acceptance still requires a private StageGuard service, least-privilege ADC invoker identity, and Docker.
- Historical full-suite failures/errors remain untriaged; there is still no full-suite green claim.

## Single best next step

**Once executable checkout is available, run and fix `runtime/tests/test_operator_console_dom.py` first. If it is green, extend the same behavioral harness to exercise the actual recheck button request path and assert that it issues only `POST /v1/recovery/recheck` and never `/v1/execute`, then fold the DOM test into the focused local safety suite without adding noisy GitHub Actions.**

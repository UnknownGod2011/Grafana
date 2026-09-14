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
- Fast local recovery-safety validation must execute the real embedded operator-console JavaScript; missing Node is an explicit validation failure rather than a silently skipped browser safety check.

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected platform-specific permission test skipped on Windows.
- Focused core/API/UI suite from the last executable repository run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating the latest hardening/recovery work.
- Historical official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`; pinned `1.4.1` still requires a live smoke.
- Current committed recovery/API/Grafana/operator regressions remain blocked from repository execution because this automation runner cannot resolve `github.com`; authenticated connector reads/writes work, but commits are not treated as passing tests.

## Run log — 2026-09-14 — focused recovery safety runner

### Inspected at start

Read this `progress.md` completely before selecting work. Inspected the repository root, `scripts/`, the current README safety/runtime description, the recovery regression inventory, `runtime/tests/test_operator_console_dom.py`, and `runtime/tests/test_operator_console_dom_requests.py`. Confirmed the two behavioral DOM harnesses existed but there was no stable explicit fast-safety entrypoint guaranteeing they run together with the service/API/restart recovery regressions.

No unrelated repository, cloud resource, Grafana instance, Gemini endpoint, remediation provider, IAM binding, or GitHub Actions workflow was modified or triggered.

### Exact changes made

1. Added `scripts/run_recovery_safety_suite.py` as a single dependency-light recovery/no-replay validation entrypoint.
2. The runner executes these committed modules together from the `runtime` working directory so their existing bare runtime imports resolve consistently:
   - `tests.test_recovery_observability`
   - `tests.test_anchored_recovery_recheck`
   - `tests.test_api_recovery_recheck`
   - `tests.test_recovery_recheck_restart`
   - `tests.test_operator_console_dom`
   - `tests.test_operator_console_dom_requests`
3. The suite therefore spans the bounded recovery observability contract, anchored/service recovery-only behavior, authenticated HTTP recheck behavior, restart durability/no-replay semantics, actual cockpit DOM interlocks, and the real browser request path.
4. The runner explicitly requires Node.js before invoking unittest. This prevents the two JavaScript behavioral safety tests from being silently accepted as skipped on machines without a JavaScript runtime.
5. The runner uses only Python stdlib + Node stdlib and does not require Grafana, Gemini, remediation credentials, Docker, browser downloads, npm packages, or paid cloud infrastructure.

Commit:
- `6e2ef3b2e6b17ad58a66b6a0c0e3517908ce9ec2` — Add focused recovery safety test runner

### Checks / results

- Authenticated GitHub connector read/write operations succeeded against `UnknownGod2011/Grafana`.
- Confirmed all six referenced recovery test modules exist on `main`; directly inspected the DOM harnesses and recovery restart/observability modules.
- Independently syntax-compiled the new runner logic with `python -m py_compile`: PASS.
- Confirmed this execution environment has Node.js `v22.16.0`, so Node itself is not the current blocker.
- Attempted a fresh shallow checkout followed by `python scripts/run_recovery_safety_suite.py`.
- Checkout failed before any repository test could run with `Could not resolve host: github.com`.
- Therefore this run does **not** claim the new focused suite green.
- No GitHub Actions workflow was triggered merely to bypass the runner DNS failure.

### Decisions

1. Recovery/no-replay safety now has one intentional local command instead of relying on developers remembering a growing list of individual modules.
2. Browser-level recovery safety is mandatory in this focused suite: absent Node is a failed prerequisite, not an acceptable skip.
3. The runner is deliberately narrow rather than pretending the historical full suite is green; it targets the highest-risk accepted-remediation/recovery boundary while legacy full-suite failures remain to be triaged separately.
4. No new CI workflow was added because the project explicitly avoids noisy Actions usage and the local runner provides the needed deterministic entrypoint without consuming CI storage/minutes.

### Blockers / unknowns

- This automation runner still cannot resolve `github.com`, so a current repository checkout and executable suite remain unavailable here.
- Recent audit/checkpoint/retention/recovery/Grafana regressions still require consolidated execution.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- The real disposable private Cloud Run acceptance still requires a private StageGuard service, least-privilege ADC invoker identity, and Docker.
- Historical full-suite failures/errors remain untriaged; there is still no full-suite green claim.

## Single best next step

**As soon as repository checkout is executable, run `python scripts/run_recovery_safety_suite.py` first and fix any failure until the full focused recovery/no-replay suite is green. Then make that command visible in the main developer/operator documentation and move to the highest-impact remaining production gap rather than adding more source-only recovery assertions.**

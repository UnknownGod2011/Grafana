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
- Execution uncertainty is resolved only by durable checkpoint reload plus server-owned provider reconciliation and fresh Grafana evidence; callers never supply provider operation identity/state.
- Fast local recovery-safety validation must execute the real embedded operator-console JavaScript; missing Node is an explicit validation failure rather than a silently skipped browser safety check.

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected platform-specific permission test skipped on Windows.
- Focused core/API/UI suite from the last executable repository run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating the latest hardening/recovery work.
- Historical official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`; pinned `1.4.1` still requires a live smoke.
- Current committed recovery/API/Grafana/operator regressions remain blocked from repository execution because this automation runner cannot resolve `github.com`; authenticated connector reads/writes work, but commits are not treated as passing tests.

## Run log — 2026-09-14 — canonical HTTP safety contract

### Inspected at start

Read this `progress.md` completely before selecting work. Inspected repository metadata/root contents, `README.md`, `FINAL_RELEASE_REPORT.md`, `EXECUTION_UNCERTAINTY.md`, `OPERATOR_CONSOLE.md`, `runtime/api.py`, `runtime/execution_safety.py`, and `runtime/tests/test_execution_safety_api.py`.

The current runtime already implements two safety-critical authenticated endpoints that are essential when provider dispatch may have happened but durable lifecycle persistence is ambiguous:

- `POST /v1/checkpoint/reload`
- `POST /v1/execution/reconcile`

Behavioral coverage proves they are authenticated, argument-free, preserve exactly-one provider dispatch, and require fresh Grafana evidence before lifecycle work can resume. However, the main HTTP surface documentation did not provide one canonical complete contract describing these endpoints alongside the newer recovery-only recheck path. That is a production operator/integrator defect because the wrong recovery action in `execution_uncertain` is to retry `/v1/execute`.

Attempted the intended fresh checkout and focused safety command first. The environment again failed during `git clone` with `Could not resolve host: github.com`, before any repository test could execute. Authenticated GitHub connector access remained available, so work continued through that channel without triggering GitHub Actions.

No unrelated repository, cloud resource, Grafana instance, Gemini endpoint, remediation provider, IAM binding, or GitHub Actions workflow was modified or triggered.

### Exact changes made

1. Added `API.md` as the canonical StageGuard HTTP contract.
2. Documented all platform probes, authenticated read surfaces, and authenticated lifecycle mutations in one place.
3. Documented the execution-uncertainty no-replay workflow explicitly: reload durable winner, reconcile the server-owned idempotent provider operation, then collect fresh Grafana evidence; never retry `/v1/execute` to resolve ambiguity.
4. Documented that `POST /v1/checkpoint/reload`, `POST /v1/execution/reconcile`, and `POST /v1/recovery/recheck` accept `{}` only and do not accept caller-supplied provider operation IDs/state.
5. Documented the separate `recovery_unverified` path: only `POST /v1/recovery/recheck` may follow an accepted-but-unverified action, and that path has no remediation client capable of redispatch.
6. Added `runtime/tests/test_http_surface_contract.py`, a dependency-free static regression that locks all platform/authenticated/lifecycle routes against both `runtime/api.py` and `API.md`.
7. Added explicit regression assertions for the no-replay documentation and for the argument-free runtime shape of recovery recheck, checkpoint reload, and execution reconciliation.

Commits:
- `8cf43f680bc95f9efb67327667afaa0bc199a8be` — Document StageGuard authenticated HTTP safety contract
- `8f1478207efc49c133b02f3c114697268e0481ee` — Lock documented StageGuard HTTP safety surface

### Checks / results

- Authenticated GitHub connector read/write operations succeeded against `UnknownGod2011/Grafana`.
- Re-fetched `runtime/tests/test_http_surface_contract.py` from `main` and confirmed the committed route set includes all current platform probes, authenticated reads, lifecycle mutations, and both execution-uncertainty endpoints.
- Cross-checked the contract against `runtime/api.py`: the documented recovery/reload/reconcile paths are real handlers, all three use `_only(payload, set())`, and reconciliation is server-owned.
- Cross-checked the no-replay statements against `runtime/execution_safety.py` and the existing behavioral `test_execution_safety_api.py`; those tests already prove reload-before-reconciliation and exactly one remediation provider dispatch.
- Syntax-compiled the new regression module shape locally with `python -m py_compile`: PASS.
- Attempted a fresh shallow checkout plus `python scripts/run_recovery_safety_suite.py`; checkout failed before tests with `Could not resolve host: github.com`.
- Therefore this run does **not** claim the new committed test or focused recovery suite green.
- No GitHub Actions workflow was triggered merely to bypass the runner DNS failure.

### Decisions

1. Treat a missing operator contract for execution uncertainty as a safety defect, not cosmetic documentation debt: during ambiguous provider execution, the recovery procedure must be unambiguous and must not encourage replay.
2. Keep operation identity/state server-owned. The new contract explicitly rejects the pattern of callers submitting provider operation IDs or reconciliation state.
3. Add a low-cost static drift test rather than a new CI workflow. The behavioral API tests remain authoritative for runtime semantics; this regression prevents future documentation/runtime divergence.
4. Do not duplicate or alter the already-covered reconciliation implementation while executable repository checkout is unavailable.

### Blockers / unknowns

- This automation runner still cannot resolve `github.com`, so a current repository checkout and executable focused suite remain unavailable here.
- Recent audit/checkpoint/retention/recovery/Grafana regressions still require consolidated execution.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- The real disposable private Cloud Run acceptance still requires a private StageGuard service, least-privilege ADC invoker identity, and Docker.
- Historical full-suite failures/errors remain untriaged; there is still no full-suite green claim.

## Single best next step

**As soon as repository checkout is executable, run `python scripts/run_recovery_safety_suite.py` plus `python -m unittest runtime.tests.test_http_surface_contract`, fix every failure to green, then stop adding recovery/documentation assertions and triage the historical full-suite failures/errors into true defects versus obsolete tests. Fix the highest-severity genuine production defect first while keeping GitHub Actions quiet.**

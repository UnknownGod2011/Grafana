# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the read-only runtime evidence plane. The implemented vertical slice includes deterministic telemetry, Prometheus/Loki/Grafana, official Grafana MCP access, bounded diagnosis, optional Gemini briefing, revision-bound approval, remediation adapters, telemetry-verified recovery, authenticated lifecycle state, checkpoint/audit integrity, operator UI, Cloud Run deployment hardening, watchdog observability, authenticated private metrics bridging, strict evidence parsing, evidence-unavailable abstention, fail-closed HTTP/operator handling, and an explicit no-replay reconciliation state for post-remediation persistence uncertainty.

Core invariants retained:
- Grafana/MCP is read-only evidence access; infrastructure write credentials remain isolated.
- Gemini is advisory and cannot mutate diagnosis, approval, remediation, or recovery state.
- Required evidence unavailability prevents Gemini briefing, approval, and execution from becoming actionable.
- Approval is exact-revision-bound and single-use.
- Provider action success never counts as recovery; fresh Grafana telemetry must prove recovery.
- Durable checkpoint/audit integrity failures fail closed.
- Append-before-CAS audit residue is not lifecycle authority until a checkpoint transition wins.
- A losing or otherwise failed persistence transition must not remain visible through `status()` as committed incident, approval, or remediation state.
- Failed checkpoint-backed transitions must not expose unauthenticated audit residue through the operator timeline.
- Once a provider action may have been dispatched, persistence uncertainty blocks replay.
- Simultaneous execution uncertainty and audit-integrity failure must preserve the no-replay barrier and be externally visible as one bounded safety state.
- The browser and HTTP API must not expose provider failure detail or turn evidence loss into actionable state.
- Private Cloud Run metrics requests must not follow redirects and must keep token audience/target boundaries explicit.
- Runtime metrics readiness requires an unambiguous StageGuard safety sentinel, not merely HTTP 200.

## Recent hardening retained

- `ExecutionSafeIncidentService` prioritizes `execution_uncertain` once provider dispatch may have occurred, even when audit integrity also failed.
- Authenticated lifecycle responses expose a bounded composite `safety_state` and a strict `sg-<40 lowercase hex>` `execution_reconciliation_reference` only when appropriate.
- `/readyz` and Prometheus expose fixed-cardinality lifecycle-safety state without exporting the reconciliation reference.
- The dedicated Prometheus remediation-uncertainty gauge now follows both checkpoint execution uncertainty and any non-clear execution-reconciliation barrier, so it cannot contradict the composite no-replay safety state.
- The operator console treats any non-`ok` composite safety state as an independent fail-closed interlock.
- `execution_uncertain_audit_failed` renders a prominent `DO NOT REPLAY REMEDIATION` state and keeps investigation, Gemini briefing, approval, and execution disabled.
- Base and anchored checkpoint-backed transition failures restore the last committed snapshot and prevent append-before-persistence residue from becoming operator-visible committed history.
- Post-provider persistence failures preserve exactly-once provider intent by entering execution uncertainty and blocking replay.
- Authenticated evidence-unavailable briefing, approval, and execution bypass attempts fail closed with no Gemini/remediation side effects.
- Cloud Run metrics bridge rejects redirects for ID-token-bearing requests and keeps token audience/target boundaries explicit.
- StageGuard metrics sentinel families reject labeled/ambiguous sibling series.
- Disposable Cloud Run acceptance scaffolding covers authenticated `/metrics` and Prometheus `up: 1 -> 0 -> 1` bridge recovery without mutating IAM or Cloud Run lifecycle state.

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected platform-specific permission test skipped on Windows.
- Focused core/API/UI suite from last executable run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating the latest checkpoint/acceptance hardening.
- Official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0` before the latest evidence-availability changes.
- Incident flow baseline: investigate -> diagnose `uplink-b packet loss` -> exact revision approval -> bounded remediation -> telemetry-verified recovered.

## Run log — 2026-09-12 — dual execution/audit fail-closed observability

### Inspected at start

Read `progress.md` completely. Inspected `runtime/execution_safety.py`, `runtime/api.py`, `runtime/remediation.py`, `runtime/tests/test_transition_failure_snapshot_authority.py`, and `runtime/tests/test_execution_reconciliation_observability.py`.

### Changes retained

- Added `execution_reconciliation_reference()` and exposed only the deterministic StageGuard `sg-<40 hex>` idempotency identity while execution is uncertain.
- Added composite lifecycle safety states: `ok`, `checkpoint_conflicted`, `audit_integrity_failed`, `execution_uncertain`, and `execution_uncertain_audit_failed`.
- Added authenticated lifecycle serialization, readiness, and one-hot fixed-cardinality metrics for composite safety state.
- Kept the reconciliation reference out of readiness and metrics.
- Changed checkpoint-state precedence so post-dispatch execution uncertainty remains the primary no-replay signal even when audit integrity also failed.
- Strengthened real post-provider failure regressions to prove exactly one provider dispatch, no committed outcome, stable reconciliation reference, and replay prevention.

Key commits: `d546729d`, `9d99d54c`, `73740581`, `fff05e28`, `a212323f`.

## Run log — 2026-09-12 — operator no-replay safety interlock

### Inspected at start

Read `progress.md` completely. Inspected `runtime/operator_console.py`, `runtime/tests/test_operator_console.py`, `runtime/tests/test_operator_integrity_policy.py`, `runtime/tests/test_operator_browser_evidence_unavailable.py`, `runtime/api.py`, and `OPERATOR_CONSOLE.md`.

### Changes retained

- Wired authenticated `safety_state` and `execution_reconciliation_reference` into the operator console.
- Unknown composite safety values fail hardened instead of falling back to `ok`.
- Added a prominent `DO NOT REPLAY REMEDIATION` panel for execution uncertainty, including the dual audit-failure state.
- Strictly validate reconciliation references client-side as `^sg-[0-9a-f]{40}$`.
- Block investigation, Gemini briefing, approval input, approval, and execution whenever composite lifecycle safety is non-`ok`.
- Keep provider URLs, raw provider operation identifiers, credentials, and arbitrary metadata out of the browser contract.
- Updated operator regressions and `OPERATOR_CONSOLE.md`.

Key commits: `b4b0efb2`, `99f50715`, `36202e93`, `79c796f8`, `35887010`, `87abf63b`.

### Validation status

A fresh checkout attempt failed before tests could run with `Could not resolve host: github.com`. No GitHub Actions workflow was created, modified, triggered, or rerun as a workaround. No green claim was made.

## Run log — 2026-09-12 — real-browser post-remediation no-replay acceptance

### Inspected at start

Read `progress.md` completely before deciding what to change. Then inspected:
- `runtime/tests/test_operator_browser_evidence_unavailable.py` for the existing optional Playwright pattern;
- `runtime/tests/test_transition_failure_snapshot_authority.py` for the real `ExecutionSafeIncidentService` post-provider persistence-failure fixture;
- `runtime/operator_console.py` for the `#execution-safety`, `#execution-reconciliation-reference`, `#judge-state`, and lifecycle-control contracts;
- `OPERATOR_CONSOLE.md` for the current operator/reconciliation documentation.

The repository was modified only under `UnknownGod2011/Grafana`.

### Finding

The no-replay operator interlock had static/unit regression coverage but no real-browser end-to-end acceptance. The missing proof was important because the safety contract spans multiple layers at once: execution-safe service state, authenticated lifecycle serialization, same-origin operator assets, browser rendering, strict reference validation, disabled mutation controls, and provider-detail redaction.

### Exact changes made

#### 1. Added real Chromium acceptance for `execution_uncertain_audit_failed`

Created `runtime/tests/test_operator_browser_execution_uncertain.py`.

The optional Playwright test starts the real authenticated StageGuard HTTP server around a real `ExecutionSafeIncidentService` and drives the service fixture through:
1. diagnosed investigation;
2. exact-revision approval;
3. one remediation-provider dispatch;
4. fresh telemetry recovery verification;
5. a deterministic failure of the final checkpoint persistence write.

The resulting state must have:
- exactly one provider call;
- no committed remediation outcome;
- `checkpoint_state == execution_uncertain`;
- `audit_integrity == failed`;
- the stable deterministic StageGuard reconciliation reference.

Chromium then loads `/console` with bearer authentication and requires:
- the `#execution-safety` panel to be visible;
- title `DO NOT REPLAY REMEDIATION`;
- the audit warning to state the remediation may already have executed;
- the displayed reconciliation reference to equal the deterministic `sg-...` operation identity;
- top proof state `DO NOT REPLAY`;
- `#investigate`, `#briefing`, `#approval-revision`, `#approve`, and `#execute` all disabled;
- provider call count to remain exactly one after page rendering;
- injected provider URL/token sentinels to be absent from both rendered text and page HTML;
- no `provider_url` or `provider_token` metadata exposed in rendered operator content.

Commit:
- `7c6c476bbf6c3da44a66253692c7732724c8f078` — test real-browser no-replay safety state.

#### 2. Documented the new browser acceptance

Updated `OPERATOR_CONSOLE.md` so the local-testing section includes `runtime/tests/test_operator_browser_execution_uncertain.py` and explains its exact end-to-end contract: one provider dispatch, simulated final persistence failure, `DO NOT REPLAY`, bounded reconciliation reference, disabled unsafe controls, and provider-detail leak prevention.

Commit:
- `b19976b52bee64eb04b09804904242470898fe8a` — document browser no-replay acceptance coverage.

### Checks / results

- The new test source was syntax-compiled before commit successfully.
- Re-read the committed test from GitHub and verified the fixture, selectors, reference assertion, disabled controls, provider-call assertion, and leak sentinels are present.
- Attempted the focused executable run with a fresh clone followed by:
  - `tests.test_operator_console`
  - `tests.test_operator_integrity_policy`
  - `tests.test_operator_browser_evidence_unavailable`
  - `tests.test_operator_browser_execution_uncertain`
  - `tests.test_transition_failure_snapshot_authority`
  - `tests.test_execution_reconciliation_observability`
- The execution container again failed at checkout with `Could not resolve host: github.com`, so none of those repository tests executed in this environment.
- No GitHub Actions workflow was created, modified, triggered, or rerun to work around the transient DNS failure.
- No GCP/IAM/Cloud Run, Grafana Cloud, Gemini provider, remediation provider, incident, audit store, or other external runtime resource was mutated.

No green repository-suite or Playwright claim is made for this run.

### Decisions

1. Keep the browser test optional so the core runtime does not acquire a Playwright dependency.
2. Exercise the real execution-safe service rather than mocking API JSON; the browser proof should cover the actual dual-failure state construction and serialization path.
3. Inject provider endpoint/token sentinels into successful remediation metadata so the browser acceptance doubles as a leak-prevention regression.
4. Preserve the existing no-replay rule: browser rendering itself must not trigger any remediation action or consume the reconciliation reference as an execution token.
5. Continue avoiding noisy CI solely to work around the transient execution-environment DNS failure.

### Blockers / unknowns

- The new Playwright acceptance still needs execution in an environment with a working repository checkout and Chromium installed.
- The operator/unit, transition-authority, and execution-reconciliation suites still need a combined current run after the latest UI and browser changes.
- The evidence-unavailable Playwright acceptance still needs a current run against the latest console assets.
- The focused Cloud Run audience/redirect/sentinel/bridge suites still need a current executable run.
- The disposable private Cloud Run acceptance still requires a private StageGuard test service, working least-privilege ADC invoker identity, and Docker.
- Historical full-suite failures/errors remain untriaged; there is still no full-suite green claim.

## Run log — 2026-09-12 — reconciliation/Prometheus safety consistency

### Inspected at start

Read `progress.md` completely before deciding what to change. Then inspected `runtime/api.py`, `runtime/tests/test_execution_reconciliation_observability.py`, `runtime/operator_console.py`, and the real-browser `runtime/tests/test_operator_browser_execution_uncertain.py` acceptance. A fresh local checkout was attempted first and again failed with `Could not resolve host: github.com`; repository inspection and writes therefore used the GitHub repository connector directly.

### Finding

`_lifecycle_safety_state()` correctly treats any non-clear execution-reconciliation state as execution uncertainty, including the dual `execution_uncertain_audit_failed` no-replay condition. The dedicated Prometheus gauge `stageguard_remediation_execution_uncertain`, however, was computed only from `checkpoint_state == "execution_uncertain"`.

That created a contradictory observability possibility: a process could expose `lifecycle_safety=execution_uncertain_audit_failed` and block operator replay while the dedicated remediation-uncertainty gauge reported `0` if the checkpoint surface still read `conflicted` and the reconciliation state remained non-clear. For a production incident commander, Grafana must not under-report the exact state that operators are told is unsafe.

### Exact changes made

1. Updated `runtime/api.py` so `stageguard_remediation_execution_uncertain` is asserted whenever either:
   - checkpoint state is `execution_uncertain`, or
   - the bounded execution reconciliation state is anything other than `clear`.

   This aligns Prometheus with the same no-replay predicate used by the lifecycle safety contract.

   Commit: `4faa33af85e4dee7274623a45f77e47233564905`.

2. Strengthened `runtime/tests/test_execution_reconciliation_observability.py` with a regression where checkpoint state remains `conflicted` while reconciliation is `reloaded`/non-clear. The test requires:
   - `stageguard_remediation_execution_uncertain 1` for the uncertain state;
   - the gauge to remain `0` for a plain checkpoint conflict with clear reconciliation;
   - the uncertain case to map to `execution_uncertain_audit_failed`;
   - the plain conflict to remain `checkpoint_conflicted`.

   The existing dual execution/audit failure test now also explicitly requires the uncertainty gauge to be `1`.

   Commit: `dd68bcc45fdcb40a6a78547a72d47156e1112459`.

### Checks / results

- Re-read the production commit diff from GitHub and confirmed it is narrowly scoped to the metric predicate; no unrelated runtime behavior changed.
- Re-read the regression commit diff and confirmed coverage includes both the non-clear reconciliation case and the clear-conflict control case.
- The local execution environment still cannot resolve `github.com`, so the focused unittest module and the broader operator/safety set could not be executed from a checkout during this run.
- No GitHub Actions workflow was created, modified, triggered, or rerun as a workaround.
- No GCP/IAM/Cloud Run, Grafana Cloud, Gemini provider, remediation provider, audit store, or other external runtime resource was mutated.
- No new green test-suite claim is made.

### Decisions

1. Treat reconciliation state as part of the canonical execution-uncertainty signal, not merely a UI concern.
2. Keep the metric fixed-cardinality and continue excluding the `sg-...` reconciliation reference from Prometheus.
3. Preserve checkpoint-conflict telemetry independently; a dual failure may legitimately assert both conflict and execution-uncertainty indicators.
4. Avoid adding new dashboard/UI features until the current safety and Cloud Run acceptance surfaces are executable again.

### Blockers / unknowns

- The modified execution-reconciliation observability regression still needs execution in a working checkout.
- Both Playwright safety acceptances and the focused operator/transition suites still need a current combined run.
- The disposable private Cloud Run acceptance still requires a private test service, least-privilege ADC invoker identity, and Docker.
- Historical full-suite failures/errors remain untriaged; there is still no full-suite green claim.

## Single best next step

**As soon as checkout execution is available, run `tests.test_execution_reconciliation_observability` first to validate the corrected Prometheus no-replay signal, then run the complete focused operator/safety set including both Playwright modules. If those are clean, move directly to the private Cloud Run `ADC -> /metrics -> bridge -> Prometheus up 1 -> 0 -> 1` acceptance rather than adding more UI surface.**

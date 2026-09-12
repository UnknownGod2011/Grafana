# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the read-only runtime evidence plane. The implemented vertical slice includes deterministic telemetry, Prometheus/Loki/Grafana, official Grafana MCP access, bounded diagnosis, optional Gemini briefing, revision-bound approval, remediation adapters, telemetry-verified recovery, authenticated lifecycle state, checkpoint/audit integrity, operator UI, Cloud Run deployment hardening, watchdog observability, authenticated private metrics bridging, strict evidence parsing, evidence-unavailable abstention, and fail-closed HTTP/operator handling.

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

## Run log — 2026-09-12 — dual execution/audit fail-closed observability

### Inspected at start

Read `progress.md` completely before deciding what to change. Then inspected:
- `runtime/execution_safety.py`, especially checkpoint-state precedence, uncertainty state, operation identity, reload, and reconciliation paths;
- `runtime/api.py`, especially authenticated lifecycle serialization, readiness, Prometheus metrics, and error fallbacks;
- `runtime/remediation.py`, especially deterministic `remediation_operation_id(...)` semantics;
- `runtime/tests/test_transition_failure_snapshot_authority.py`;
- `runtime/tests/test_execution_reconciliation_observability.py`;
- the runtime test inventory to avoid redundant coverage.

### Finding

After a provider action may have been dispatched, a non-CAS persistence failure can legitimately produce two simultaneous barriers:
1. `audit_integrity=failed`, because the lifecycle/audit transition did not persist safely;
2. `execution_uncertain`, because the remote remediation may already have happened and must never be replayed blindly.

Before this run, `ExecutionSafeIncidentService.checkpoint_state()` prioritized audit failure and returned only `conflicted`. That obscured the more safety-critical no-replay condition and could make the legacy `stageguard_remediation_execution_uncertain` metric read `0` despite a provider action potentially having occurred. The stable deterministic StageGuard operation identity already existed internally but was not available to an authenticated operator for reconciliation.

### Exact changes made

#### 1. Exposed a bounded StageGuard reconciliation reference

Updated `runtime/execution_safety.py` with `execution_reconciliation_reference()`.

The method returns the already-existing deterministic `sg-<40 lowercase hex>` idempotency identity only while execution is uncertain. It does not expose provider response bodies, URLs, credentials, arbitrary metadata, or human identity.

Commit:
- `d546729dbc7bb9f73f6513d25265baa9e3bb370e` — expose stable execution reconciliation reference.

#### 2. Added one explicit composite lifecycle safety contract

Updated `runtime/api.py` with the bounded states:
- `ok`
- `checkpoint_conflicted`
- `audit_integrity_failed`
- `execution_uncertain`
- `execution_uncertain_audit_failed`

Authenticated lifecycle responses now include:
- `safety_state` — the composite state;
- `execution_reconciliation_reference` — validated strictly as `sg-` plus 40 lowercase hex characters or omitted as `null`.

Malformed references fail closed to `null`, preventing provider URLs, tokens, or arbitrary detail from leaking through the new field.

`/readyz` now includes `checks.lifecycle_safety` and fails readiness whenever the composite state is not `ok`.

`/metrics` now exports a fixed-cardinality one-hot metric:
- `stageguard_lifecycle_safety_state{state="..."}`

The operation reference is deliberately excluded from metrics so it cannot become a high-cardinality label/sample or leak through public observability endpoints.

Commit:
- `9d99d54cdbd018acb3323bbe3572f75c82a23346` — surface composite lifecycle safety state.

#### 3. Preserved the no-replay state as the primary checkpoint state

Updated `ExecutionSafeIncidentService.checkpoint_state()` so `execution_uncertain` takes precedence over audit failure once provider dispatch may have happened. Audit failure remains independently visible through `audit_integrity`, and the API combines both into `execution_uncertain_audit_failed`.

This preserves the existing execution-uncertainty metric and makes the most safety-critical operator instruction unambiguous: **do not replay remediation**.

Commit:
- `73740581d14012d86b9490db4559b1e829c0d9f8` — prioritize execution uncertainty in checkpoint state.

#### 4. Added fixed-cardinality and leak-prevention observability regressions

Expanded `runtime/tests/test_execution_reconciliation_observability.py` to cover:
- every composite lifecycle safety state;
- the simultaneous `execution_uncertain_audit_failed` state;
- readiness failure for that state;
- exactly one active lifecycle-safety metric series across a fixed enum;
- absence of the operation reference from metrics;
- rejection of malformed/provider-detail reconciliation references;
- execution-safe reference getter behavior.

Commit:
- `fff05e286a49754d8a9636047a798c1ecf3bd1f7` — test composite execution safety observability.

#### 5. Bound the contract to the real post-provider failure path

Strengthened `runtime/tests/test_transition_failure_snapshot_authority.py` so the deterministic real `ExecutionSafeIncidentService` post-provider persistence failure now requires:
- exactly one provider call;
- committed approved/no-outcome snapshot remains authoritative;
- `audit_integrity=failed`;
- `checkpoint_state=execution_uncertain`;
- `execution_reconciliation_state=reloaded`;
- stable reference exactly equals `remediation_operation_id(report, approval)`;
- authenticated lifecycle serialization reports `execution_uncertain_audit_failed` and the same reference;
- a blocked replay leaves both provider call count and operation reference unchanged.

Commit:
- `a212323f6dcd21773b387da5749173b09797dbba` — assert dual post-dispatch safety contract.

### Checks / results

- Re-read the current `runtime/api.py` after replacement through the GitHub connector and verified the original authenticated handler routing, `/healthz`, `/readyz`, `/metrics`, `/v1/incident`, audit, investigate, briefing, approval, execution, reload, and reconciliation endpoints remain present.
- Re-read the new API helper/serialization path and confirmed the reconciliation reference is validated to the fixed StageGuard hash shape before serialization and is not included in Prometheus metrics.
- Attempted a fresh local checkout with `git clone --depth 1 https://github.com/UnknownGod2011/grafana.git`; the execution container again failed with `Could not resolve host: github.com`.
- Because checkout remains unavailable, the new/modified unittest modules could not be executed in this run.
- No GitHub Actions workflow was created, modified, triggered, or rerun as a workaround.
- No GCP/IAM/Cloud Run, Grafana Cloud, Gemini provider, incident, remediation, or external audit resource was mutated.

No green repository-suite claim is made for this run.

### Decisions

1. Once provider dispatch may have occurred, `execution_uncertain` is the primary checkpoint state because preventing duplicate infrastructure mutation is the highest-priority operational invariant.
2. Audit integrity remains a separate first-class state; the externally consumable composite state represents both barriers without losing either.
3. Composite lifecycle state is fixed-cardinality so Grafana dashboards/alerts can consume it safely.
4. The stable reconciliation identity may appear only in authenticated lifecycle responses and only in strict `sg-<40 hex>` form; it must never appear in readiness or Prometheus metrics.
5. Preserve all existing detailed checkpoint, audit, phase, and reconciliation fields for compatibility and diagnostics; `safety_state` is a single operator summary rather than a replacement.
6. Continue avoiding noisy CI solely to work around the transient execution-environment DNS failure.

### Blockers / unknowns

- `runtime/tests/test_execution_reconciliation_observability.py` and `runtime/tests/test_transition_failure_snapshot_authority.py` need execution from a real repository checkout.
- The base and anchored transition-authority/execution-safety suites should be run together after the checkpoint-state precedence change.
- The operator console does not yet visibly elevate the new `safety_state` or reconciliation reference into a dedicated high-severity no-replay banner/workflow.
- The complete evidence-unavailable safety set still needs a current combined executable run.
- The focused Cloud Run audience/redirect/sentinel/bridge suites need a current executable run.
- The disposable private Cloud Run acceptance requires a private StageGuard test service, working ADC for a least-privilege invoker identity, and Docker.
- Playwright evidence-unavailable browser acceptance still needs execution with Chromium.
- Historical full-suite failures/errors have not yet been re-triaged; there is no full-suite green claim.

## Single best next step

**Wire `safety_state` and the bounded `execution_reconciliation_reference` into the operator console. For `execution_uncertain_audit_failed`, show one high-severity “DO NOT REPLAY REMEDIATION” state that explains the audit write is untrusted, preserves the stable `sg-...` reconciliation reference for operator/provider correlation, and disables unsafe lifecycle actions. Add operator/UI regressions without exposing the reference in public readiness or metrics; then run the transition-authority and execution-safety suites together as soon as checkout execution is available.**

## Recent hardening retained

- Simultaneous audit-integrity failure and post-provider execution uncertainty now have an explicit composite lifecycle safety state.
- Stable remediation reconciliation identity is available to authenticated operators only and excluded from public metrics/readiness.
- Base checkpoint-backed non-CAS transition failures no longer expose uncommitted investigation, approval, or remediation snapshots.
- Base failed-integrity timeline reads no longer surface raw append-before-persistence residue as committed history.
- Production anchored non-CAS transition failures no longer expose uncommitted lifecycle snapshots or unauthenticated audit tail as committed operator history.
- Base and production anchored remediation outcome CAS losers no longer remain visible through `status()` as committed state.
- Investigation and approval CAS losers no longer remain visible through `status()` as committed state.
- Authenticated evidence-unavailable briefing, approval, and execution bypass attempts fail closed with no Gemini/remediation side effects.
- Cloud Run metrics bridge rejects redirects for ID-token-bearing requests.
- Cloud Run token audience must match target origin by default unless explicitly opted out.
- StageGuard metrics sentinel families reject labeled/ambiguous sibling series.
- Disposable Cloud Run acceptance scaffolding covers authenticated `/metrics` and Prometheus `up: 1 -> 0 -> 1` bridge recovery without mutating IAM or Cloud Run lifecycle state.

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected platform-specific permission test skipped on Windows.
- Focused core/API/UI suite from last executable run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating the latest checkpoint/acceptance hardening.
- Official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0` before the latest evidence-availability changes.
- Incident flow baseline: investigate -> diagnose `uplink-b packet loss` -> exact revision approval -> bounded remediation -> telemetry-verified recovered.

## Run log — 2026-09-12 — operator no-replay safety interlock

### Inspected at start

Read this file completely before changing the repository. Inspected the current repository head and tree, then focused on:
- `runtime/operator_console.py` and its existing checkpoint, audit-integrity, evidence-unavailable, approval, execution, timeline, and proof-layer behavior;
- `runtime/tests/test_operator_console.py`;
- `runtime/tests/test_operator_integrity_policy.py`;
- `runtime/tests/test_operator_browser_evidence_unavailable.py` to preserve the existing real-browser abstention contract;
- `runtime/api.py` lifecycle serialization and authenticated console asset routing;
- `OPERATOR_CONSOLE.md`.

The repository was modified only under `UnknownGod2011/Grafana`.

### Finding

The API now exposes the correct composite `safety_state` and a strictly bounded authenticated `execution_reconciliation_reference`, but the operator console still reasoned mainly from the older checkpoint/audit fields. That left the highest-risk dual state — `execution_uncertain_audit_failed` — without a single unmistakable browser instruction. An operator needed one explicit safety contract: the provider may already have acted, the durable write is not trusted, and remediation must not be replayed.

### Exact changes made

#### 1. Added a high-severity authenticated no-replay interlock

Updated `runtime/operator_console.py` so the console consumes:
- `safety_state`;
- `execution_reconciliation_reference`.

The console recognizes only the fixed lifecycle enum and treats an unknown safety state as `audit_integrity_failed` rather than optimistic `ok`.

For `execution_uncertain` and especially `execution_uncertain_audit_failed`, it renders a prominent `DO NOT REPLAY REMEDIATION` safety panel. The dual state explicitly tells the operator that provider dispatch may already have occurred while the audit/checkpoint transition is untrusted.

The reconciliation reference is accepted only when it matches `^sg-[0-9a-f]{40}$`; malformed or arbitrary values render as unavailable. Provider URLs, raw provider operation identifiers, credentials, and arbitrary metadata are not accepted by the browser contract.

The composite safety state is now an independent lifecycle block in addition to checkpoint and audit policy state. Investigation, Gemini briefing, approval input, approval, and execution remain disabled while the composite state is non-`ok`.

The top proof/status surface also elevates `execution_uncertain_audit_failed` to `DO NOT REPLAY` instead of allowing an approval/recovery-looking state to dominate.

Primary implementation commit:
- `b4b0efb22a7ecf3995b4107e96d60c5a7bcd22cd` — surface no-replay lifecycle safety in operator console.

The console was subsequently reviewed against the prior proof-layer behavior before the final branch state was selected; no unrelated repository was touched and no external resource was mutated.

#### 2. Updated operator regressions for the composite contract

Updated `runtime/tests/test_operator_console.py` to require:
- the dedicated no-replay panel and reconciliation-reference surface;
- strict `sg-<40 lowercase hex>` client validation;
- consumption of `data.safety_state` and `data.execution_reconciliation_reference`;
- `execution_uncertain_audit_failed` guidance;
- the composite state participating in the common lifecycle block;
- briefing, approval, and execution remaining disabled under that block;
- no `operation_id` or `provider_url` in console HTML/JavaScript;
- existing authenticated checkpoint reload/reconciliation endpoints remaining body-empty and server-authoritative.

Updated `runtime/tests/test_operator_integrity_policy.py` so hardened audit policy is tested together with the composite safety block and unknown server values are required to fall back to hardened states.

Commits:
- `99f507153bfc1ae928effdb509d240d86fcd75ed` — test composite no-replay operator interlock;
- `36202e9355fab28a0a455ad4fcf6235e3f9d256d` — align operator integrity tests with composite safety contract;
- `79c796f8dbff1a236c9946bfcaf14d5dc2d7582a` — fix bounded reconciliation reference regression.

#### 3. Documented operator reconciliation semantics

Updated `OPERATOR_CONSOLE.md` with the no-replay remediation interlock, strict bounded-reference behavior, dual audit/execution failure guidance, and the requirement that the reference remain out of readiness and Prometheus metrics.

Commit:
- `35887010cbfadfd597cab57ce9dfc0d244d1ad45` — document no-replay operator interlock.

#### 4. Reviewed and normalized the final console tree

A repository-tree review was performed after the UI/test changes. The branch remained fast-forward only. The current console/test/document tree was finalized in:
- `87abf63b3ae2a77dc6e12b53906e6c598da6b177` — apply no-replay operator safety console.

### Checks / results

- Confirmed the resulting comparison from the previous handoff changes only `OPERATOR_CONSOLE.md`, `runtime/operator_console.py`, `runtime/tests/test_operator_console.py`, and `runtime/tests/test_operator_integrity_policy.py`.
- Re-read the authenticated console routing in `runtime/api.py`; `/console`, `/assets/operator.js`, and `/assets/operator.css` remain behind the configured identity provider and retain no-store/CSP handling.
- Preserved the evidence-unavailable browser contract: the current console still exposes `#judge-state` / `#judge-root-cause` and explicitly renders `EVIDENCE UNAVAILABLE` / `Not established` for an abstained incident.
- Attempted a fresh checkout and focused test run with `git clone --depth 1 https://github.com/UnknownGod2011/Grafana.git` followed by the operator unittest modules. The execution container failed before checkout with `Could not resolve host: github.com`.
- No GitHub Actions workflow was created, modified, triggered, or rerun to work around the DNS failure.
- No GCP/IAM/Cloud Run, Grafana Cloud, Gemini, remediation provider, incident, audit store, or other external runtime resource was mutated.

No green test-suite claim is made for this run. The committed operator regressions still need execution from a checkout-capable environment.

### Decisions

1. The browser treats `safety_state` as an independent fail-closed interlock rather than merely informational text.
2. Unknown composite safety values fail hardened instead of falling back to `ok`.
3. The only operation correlation value permitted into the authenticated browser is the StageGuard-generated `sg-<40 lowercase hex>` reconciliation reference.
4. The reconciliation reference is display/correlation data only; the browser does not submit it as a remediation operation identifier and does not expose provider details.
5. Dual `execution_uncertain_audit_failed` state prioritizes the operator instruction **DO NOT REPLAY REMEDIATION** while retaining the separate audit-integrity explanation.
6. Continue avoiding noisy CI solely to work around the transient local DNS failure.

### Blockers / unknowns

- The updated `test_operator_console.py` and `test_operator_integrity_policy.py` need a real executable run.
- The existing Playwright evidence-unavailable browser acceptance needs execution against the updated console assets.
- The transition-authority and execution-safety suites from the previous run still need a combined executable run.
- The focused Cloud Run audience/redirect/sentinel/bridge suites still need a current executable run.
- The disposable private Cloud Run acceptance still requires a private test service, working least-privilege ADC invoker identity, and Docker.
- Historical full-suite failures/errors remain untriaged; there is still no full-suite green claim.

## Single best next step

**As soon as repository checkout works, run `tests.test_operator_console`, `tests.test_operator_integrity_policy`, `tests.test_operator_browser_evidence_unavailable`, the execution/transition-authority regressions, and the API lifecycle-safety regressions together. Fix any integration mismatch before adding more features; then add a real-browser `execution_uncertain_audit_failed` acceptance that proves the `DO NOT REPLAY` panel is visible, the strict `sg-...` reference is rendered, and every unsafe lifecycle control remains disabled without leaking provider detail.**

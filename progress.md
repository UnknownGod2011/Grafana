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

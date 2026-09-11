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
- A losing optimistic-concurrency writer must not remain visible through `status()` as if its incident revision, approval, or remediation outcome were committed.
- Once a provider action may have been dispatched, checkpoint uncertainty blocks replay until durable reload/reconciliation.
- The browser and HTTP API must not expose provider failure detail or turn evidence loss into actionable state.
- Private Cloud Run metrics requests must not follow redirects and must keep token audience/target boundaries explicit.
- Runtime metrics readiness requires an unambiguous StageGuard safety sentinel, not merely HTTP 200.

## Run log — 2026-09-12 — central remediation outcome checkpoint authority

### Inspected at start

Read `progress.md` completely before deciding what to change. Then inspected:
- `runtime/incident_service.py`, especially `_record()`, `_record_snapshot_transition()`, `approve()`, and `execute_approved()`;
- `runtime/execution_safety.py`, including the `dispatching` barrier and post-provider uncertainty handling;
- `runtime/tests/test_execution_safety.py`;
- the previously hardened production path in `runtime/anchored_execution_safety.py` indirectly through the recorded handoff and current base-service contract.

### Finding

The previous run hardened the production `AnchoredExecutionSafeIncidentService`, but the base `IncidentService.execute_approved()` still assigned the remediation outcome directly to `self._snapshot` before `remediation_completed` checkpoint persistence completed.

`ExecutionSafeIncidentService` calls this base method after its pre-provider safety barrier. Therefore a losing final checkpoint CAS could still leave the non-anchored composition temporarily exposing an outcome that never became durable lifecycle authority, even though the service correctly entered execution uncertainty and refused provider replay.

### Exact changes made

#### Centralized base outcome publication through checkpoint-authoritative transition

Updated `runtime/incident_service.py`.

After provider execution and Grafana recovery verification, `execute_approved()` now:
1. constructs an immutable candidate `IncidentSnapshot` containing the outcome;
2. builds the existing bounded remediation audit payload;
3. publishes the candidate only through `_record_snapshot_transition(...)`;
4. automatically restores the previous approved/no-outcome snapshot when the checkpoint CAS loses;
5. returns the committed candidate only when the transition succeeds.

This centralizes the same read-authority invariant already used for investigation and approval. It also means checkpoint-backed subclasses such as `ExecutionSafeIncidentService` inherit the non-authoritative-loser behavior without duplicating outcome-publication logic.

Commit:
- `b782a45718abb9df2386aabe756eb1e619c72eb5` — make base remediation outcome checkpoint authoritative.

#### Strengthened non-anchored execution-safety regression

Updated `runtime/tests/test_execution_safety.py`.

`test_post_action_checkpoint_conflict_enters_execution_uncertain` now additionally requires, immediately after the provider is called once and the final checkpoint CAS loses:
- `service.status().outcome is None`;
- the prior explicit approval remains the visible lifecycle authority;
- `remediation_completed` is absent from the operator-visible committed audit timeline.

Existing assertions still require execution uncertainty, explicit reload, and zero provider replay.

Commit:
- `987710e900d5394e7bae0cd482d4d7a339759656` — test base remediation outcome checkpoint authority.

### Checks / results

- Reviewed the two-commit GitHub compare from the previous handoff commit `cbafe491533d0cdd2da6e735a10397dfed378b94` through `987710e900d5394e7bae0cd482d4d7a339759656`.
- Diff scope is narrow: `runtime/incident_service.py` is +7/-3 and `runtime/tests/test_execution_safety.py` is +4/-0.
- Attempted a fresh local checkout before editing; the execution container again failed with `Could not resolve host: github.com`.
- Because checkout is unavailable, the focused unittest suite could not be executed in this run.
- No GitHub Actions workflow was created, modified, triggered, or rerun as a workaround.
- No GCP/IAM/Cloud Run, Grafana Cloud, Gemini provider, incident, remediation, or external audit resource was mutated.

No green repository-suite claim is made for this run.

### Decisions

1. Keep lifecycle read authority centralized in `_record_snapshot_transition(...)` rather than duplicating CAS rollback logic in every subclass.
2. Keep execution uncertainty independent from visible outcome authority: a provider may have acted even when the outcome checkpoint did not commit, so replay remains forbidden.
3. Preserve append-before-CAS audit residue for durable lineage reconstruction while excluding the losing event from the committed operator timeline.
4. Avoid CI solely to work around a transient execution-environment DNS failure.

### Blockers / unknowns

- The strengthened `runtime/tests/test_execution_safety.py` regression still needs execution from a real repository checkout.
- The production anchored outcome-authority regression also still needs a current executable run.
- The complete evidence-unavailable safety set still needs a current combined executable run.
- The focused Cloud Run audience/redirect/sentinel/bridge suites need a current executable run.
- The disposable private Cloud Run acceptance requires a private StageGuard test service, working ADC for a least-privilege invoker identity, and Docker.
- Playwright evidence-unavailable browser acceptance still needs execution with Chromium.
- Historical full-suite failures/errors have not yet been re-triaged; there is no full-suite green claim.

## Single best next step

**Harden `_record_snapshot_transition(...)` for non-CAS persistence/audit failures after a candidate snapshot has been installed. Today it restores the previous snapshot only for `CheckpointConflictError`; an audit sink failure, integrity-chain failure, or other checkpoint persistence exception can still leave an uncommitted candidate visible. Add focused regressions proving investigation, approval, and remediation outcome candidates all roll back read authority on any failed transition while preserving the appropriate fail-closed integrity/execution state. Then run the base and anchored execution-safety suites together when checkout execution is available.**

## Recent hardening retained

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

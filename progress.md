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

## Run log — 2026-09-12 — remediation outcome checkpoint authority

### Inspected at start

Read `progress.md` completely before deciding what to change. Then inspected:
- `runtime/incident_service.py`, especially `_record()`, `_record_snapshot_transition()`, checkpoint persistence, and `execute_approved()`;
- `runtime/incident_checkpoint.py`, including the authenticated `execution_phase` state machine (`approved`, `dispatching`, `resolved`);
- `runtime/execution_safety.py`, including the pre-provider `dispatching` barrier, conflict reload, and provider reconciliation semantics;
- `runtime/anchored_execution_safety.py`, the production composition that releases the lifecycle lock during provider/recovery I/O;
- `runtime/tests/test_execution_safety.py` and `runtime/tests/test_anchored_execution_safety.py` for existing no-replay and watchdog coverage;
- `runtime/remediation.py` to confirm stable idempotency operation IDs and recovery verification behavior.

### Finding

The production `AnchoredExecutionSafeIncidentService.execute_approved()` correctly persisted a `dispatching` checkpoint before provider contact and correctly entered `execution_uncertain` when the final checkpoint CAS failed. However, after provider execution and Grafana recovery verification succeeded, it assigned the candidate outcome directly to `self._snapshot` before appending `remediation_completed` and persisting the final checkpoint.

If that final CAS lost, the service correctly blocked further mutations, but `status()` could still expose the losing/uncommitted outcome until an explicit durable reload. This is the same lifecycle-authority hazard previously fixed for investigation and approval, with an additional constraint: the provider side effect is irreversible, so the solution must restore read authority without ever making the action eligible for replay.

### Exact changes made

#### Production outcome publication is now checkpoint-authoritative

Updated `runtime/anchored_execution_safety.py`.

The final remediation transition now:
1. creates an immutable candidate `IncidentSnapshot` containing the outcome;
2. publishes it through the existing `_record_snapshot_transition(...)` helper;
3. lets that helper temporarily install the candidate only while serializing/persisting the checkpoint;
4. restores the pre-execution approved snapshot automatically on `CheckpointConflictError`;
5. still marks execution as uncertain with the stable provider operation ID and durable `dispatching` semantics, so the already-contacted provider cannot be replayed;
6. also restores the pre-execution snapshot on other final-commit failures after provider contact, while preserving the fail-closed execution-uncertainty barrier.

This separates two facts that must not be conflated:
- the provider may already have acted, therefore execution is uncertain and replay is forbidden;
- the outcome checkpoint did not win, therefore the candidate outcome is not lifecycle read authority.

Commit:
- `1ffb1ca37c09ce50092ee7dfd8f25196b668447c` — keep losing remediation outcomes non-authoritative.

The commit diff was reviewed after writing. The executable change is limited to replacing direct outcome assignment/recording with checkpoint-authoritative candidate publication and restoring the prior snapshot on non-CAS finalization failures.

#### Deterministic regression for post-dispatch CAS loss

Added `runtime/tests/test_execution_outcome_checkpoint_authority.py`.

The test uses:
- a phase-capable checkpoint store that accepts the pre-provider `dispatching` barrier but rejects the first checkpoint containing a remediation outcome;
- a production-style remediation fake with `requires_operation_reconciliation = True` and idempotent execution;
- deterministic diagnosed and recovery telemetry;
- the real `AnchoredExecutionSafeIncidentService` and anchored JSONL audit sink.

It proves that after the provider was called exactly once and the final outcome CAS loses:
- `status().outcome` remains `None`;
- the approved snapshot remains the visible lifecycle state;
- durable checkpoint state remains `execution_phase == "dispatching"` with no outcome;
- service readiness/lifecycle state becomes `execution_uncertain`;
- reconciliation state is `reload_required`;
- operator execution phase remains `dispatching`;
- append-before-CAS `remediation_completed` loser residue does not enter committed operator history;
- a second execution attempt is blocked and does not call the provider again;
- after explicit conflict reload, the durable no-outcome winner remains authoritative;
- reload alone still does not permit provider replay.

Commit:
- `a21290e188af6a22d7662919eb59d9358e5146f9` — test remediation outcome checkpoint authority.

### Checks / results

- Reviewed the actual GitHub commit diff for `runtime/anchored_execution_safety.py`; no unrelated executable changes were present.
- Re-read the committed regression file from `main` after creation.
- Attempted a focused executable run with:

```bash
git clone --depth 1 https://github.com/UnknownGod2011/Grafana.git /tmp/stageguard
cd /tmp/stageguard/runtime
python -m unittest \
  tests.test_execution_outcome_checkpoint_authority \
  tests.test_anchored_execution_safety \
  tests.test_execution_safety
```

- The execution container again failed before checkout with `Could not resolve host: github.com`.
- No GitHub Actions workflow was created, modified, triggered, or rerun as a workaround.
- No GCP/IAM/Cloud Run, Grafana Cloud, Gemini provider, incident, remediation, or external audit resource was mutated.

No green repository-suite claim is made for this run.

### Decisions

1. Treat final remediation outcome publication as checkpoint-authoritative just like investigation/approval publication.
2. Do **not** roll back execution uncertainty when rolling back the visible outcome. Provider contact may already have occurred; the no-replay barrier must survive independently of read authority.
3. Preserve the durable `dispatching` checkpoint as the correct crash/restart truth when the final outcome commit loses.
4. Preserve append-before-CAS audit residue for forensic lineage selection, but keep it out of committed operator history until a checkpoint transition wins.
5. Harden the production anchored composition first because it is the path designed for long-running provider calls, watchdog observability, authenticated audit anchors, and responsive reads.
6. Avoid CI solely to work around the transient execution-environment DNS failure.

### Blockers / unknowns

- `runtime/tests/test_execution_outcome_checkpoint_authority.py` still needs execution from a real repository checkout.
- The non-anchored `ExecutionSafeIncidentService` still directly inherits the base `IncidentService.execute_approved()` outcome-publication behavior; its post-action conflict semantics should be reviewed for the same read-authority invariant even though the production composition is now hardened.
- The complete evidence-unavailable safety set still needs a current combined executable run.
- The focused Cloud Run audience/redirect/sentinel/bridge suites need a current executable run.
- The disposable private Cloud Run acceptance still requires a private StageGuard test service, working ADC for a least-privilege invoker identity, and Docker.
- Playwright evidence-unavailable browser acceptance still needs execution with Chromium.
- Historical full-suite failures/errors have not yet been re-triaged; there is no full-suite green claim.

## Single best next step

**Extend the same non-authoritative-loser outcome guarantee to the non-anchored `ExecutionSafeIncidentService` / base execution path, preferably by routing base `IncidentService.execute_approved()` through `_record_snapshot_transition(...)` so every checkpoint-backed composition gets the invariant centrally. Add/strengthen a focused regression that asserts `status().outcome is None` immediately after a post-provider checkpoint conflict while provider call count remains exactly one. Then run the production and non-anchored execution-safety suites together when checkout execution becomes available.**

## Recent hardening retained

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

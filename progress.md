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
- Unauthenticated audit residue must not be presented as committed operator timeline history.
- Once a provider action may have been dispatched, checkpoint uncertainty blocks replay until durable reload/reconciliation.
- The browser and HTTP API must not expose provider failure detail or turn evidence loss into actionable state.
- Private Cloud Run metrics requests must not follow redirects and must keep token audience/target boundaries explicit.
- Runtime metrics readiness requires an unambiguous StageGuard safety sentinel, not merely HTTP 200.

## Run log — 2026-09-12 — anchored non-CAS persistence failure authority

### Inspected at start

Read `progress.md` completely before deciding what to change. Then inspected:
- `runtime/incident_service.py`, especially `_record()`, `_record_snapshot_transition()`, `_require_checkpoint_consistency()`, and `audit_timeline()`;
- `runtime/anchored_incident_service.py`, especially anchored checkpoint/anchor promotion and restore behavior;
- `runtime/anchored_execution_safety.py`, including the existing generic post-provider failure rollback and execution-uncertainty path;
- `runtime/tests/test_checkpoint_conflict_snapshot_authority.py`;
- `runtime/tests/test_audit_integrity.py`;
- `runtime/tests/test_anchored_incident_runtime.py`;
- `runtime/tests/test_anchored_execution_safety.py`.

### Finding

The previous hardening correctly restored the previous snapshot when an optimistic CAS lost. However the base `_record_snapshot_transition()` catches only `CheckpointConflictError`.

For the production anchored composition, a different persistence failure can occur after the candidate snapshot is installed and after the audit sequence/chain has advanced—for example an audit/checkpoint storage I/O failure. Before this run, that path could leave the candidate visible through `status()` even though it never became durable lifecycle authority.

A second consequence existed in anchored mode: once integrity became failed, the inherited `audit_timeline()` could fall back to the durable audit reader. Because audit append intentionally happens before checkpoint persistence, that fallback could surface the failed transition's unauthenticated append as if it were committed operator history.

### Exact changes made

#### Production anchored transition rollback for every non-CAS failure

Updated `runtime/anchored_incident_service.py`.

`AnchoredIncidentService._record_snapshot_transition(...)` now wraps the base transition contract:
1. captures the previously committed in-process snapshot;
2. delegates to the existing base transition;
3. preserves the existing explicit CAS-conflict behavior unchanged;
4. on any other transition failure, restores the previous snapshot;
5. marks audit integrity `failed`, which blocks subsequent lifecycle mutation through the existing consistency gate.

This intentionally fails closed rather than pretending a transient non-CAS storage failure has a safe authenticated winner that can be adopted through `reload_checkpoint_after_conflict()`.

Commit:
- `33cba369278a1687fd380c9a8f64fd2c83e74b27` — fail closed on anchored lifecycle transition persistence errors.

#### Fail closed timeline reads after anchored integrity failure

Also updated `runtime/anchored_incident_service.py`.

The anchored service now overrides `audit_timeline(...)` and rejects timeline reads while audit integrity is `failed`. This prevents append-before-persistence residue from being presented as committed operator history after a failed non-CAS transition.

Commit:
- `c17daa03434479420282919bbe368b08e2678a0e` — hide unauthenticated audit tail after anchored persistence failure.

#### Added deterministic non-CAS authority regressions

Added `runtime/tests/test_anchored_transition_failure_authority.py`.

The new tests use a checkpoint store that succeeds once and then raises a non-CAS `RuntimeError` while retaining the last durable checkpoint. They cover:
- failed re-investigation: the previously committed incident snapshot remains visible and the durable checkpoint revision is unchanged;
- failed approval: the uncommitted approval is never visible through `status()` and never enters the durable checkpoint;
- the append-before-persistence audit residue is still physically present for forensic recovery;
- integrity becomes `failed`;
- operator timeline reads fail closed instead of surfacing the unauthenticated tail;
- further lifecycle mutation remains blocked by the existing audit-integrity consistency gate.

Commit:
- `3683fca8b0cebb6e251aa8a1d8ba46a5ecb72e8b` — test anchored non-CAS transition failure authority.

### Checks / results

- GitHub compare from the previous handoff `00b97b769a8499c03cbf97d6659fe642a53aa18d` through `3683fca8b0cebb6e251aa8a1d8ba46a5ecb72e8b` is exactly three commits ahead and touches only:
  - `runtime/anchored_incident_service.py`: +38/-0;
  - `runtime/tests/test_anchored_transition_failure_authority.py`: +136/-0.
- Re-read the production anchored and base transition paths before implementing the change.
- Attempted a fresh local checkout before executable validation; the execution container still failed with `Could not resolve host: github.com`.
- Because checkout remains unavailable, the new unittest module and the focused anchored suites could not be executed in this run.
- No GitHub Actions workflow was created, modified, triggered, or rerun as a workaround.
- No GCP/IAM/Cloud Run, Grafana Cloud, Gemini provider, incident, remediation, or external audit resource was mutated.

No green repository-suite claim is made for this run.

### Decisions

1. Production anchored lifecycle state fails closed on every non-CAS transition failure: previous committed snapshot remains read authority and further mutation is blocked.
2. Keep CAS contention distinct from storage/integrity failure. CAS still uses the explicit conflict/reload path and does not automatically become an integrity failure.
3. Preserve append-before-persistence residue for durable forensic reconstruction; do not silently delete or rewrite it.
4. When anchored audit integrity is failed, prefer no operator timeline over an unauthenticated timeline.
5. Avoid noisy CI solely to work around transient execution-environment DNS failure.

### Blockers / unknowns

- `runtime/tests/test_anchored_transition_failure_authority.py` still needs execution from a real repository checkout.
- The base non-anchored `IncidentService` still restores failed snapshot transitions only for `CheckpointConflictError`; production anchored mode is now protected, but the invariant is not yet centralized for every composition.
- The production anchored and base execution-safety suites still need a current executable run.
- The complete evidence-unavailable safety set still needs a current combined executable run.
- The focused Cloud Run audience/redirect/sentinel/bridge suites need a current executable run.
- The disposable private Cloud Run acceptance requires a private StageGuard test service, working ADC for a least-privilege invoker identity, and Docker.
- Playwright evidence-unavailable browser acceptance still needs execution with Chromium.
- Historical full-suite failures/errors have not yet been re-triaged; there is no full-suite green claim.

## Single best next step

**Centralize the same non-CAS transition rollback invariant in base `IncidentService` so every checkpoint-backed composition—not only anchored production—restores the previous snapshot and enters an explicit fail-closed persistence/integrity state after audit/checkpoint failure. Add focused base regressions for investigation, approval, and remediation outcome persistence failures, while ensuring `ExecutionSafeIncidentService` still marks post-provider failures `execution_uncertain` and never replays the provider action. Then run the new anchored/base suites together when checkout execution is available.**

## Recent hardening retained

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

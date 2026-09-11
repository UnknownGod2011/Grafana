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
- The browser and HTTP API must not expose provider failure detail or turn evidence loss into actionable state.
- Private Cloud Run metrics requests must not follow redirects and must keep token audience/target boundaries explicit.
- Runtime metrics readiness requires an unambiguous StageGuard safety sentinel, not merely HTTP 200.

## Run log — 2026-09-12 — base transition persistence authority

### Inspected at start

Read `progress.md` completely before deciding what to change. Then inspected:
- `runtime/incident_service.py`, especially `_record()`, `_record_snapshot_transition()`, `_require_checkpoint_consistency()`, `audit_timeline()`, investigation, approval, and remediation completion;
- `runtime/execution_safety.py`, especially the provider-dispatch wrapper and generic post-provider failure path;
- `runtime/tests/test_checkpoint_conflict_snapshot_authority.py`;
- `runtime/tests/test_execution_safety.py`;
- the immediately preceding anchored persistence-failure handoff.

### Finding

The anchored production composition already restored the previous committed snapshot on non-CAS transition failure, but the base `IncidentService` still restored only `CheckpointConflictError` failures.

That meant any other audit/checkpoint failure after the candidate snapshot was installed could leave an uncommitted investigation, approval, or remediation outcome visible through `status()` in non-anchored checkpoint-backed compositions. The base timeline also still had a raw-reader fallback that could present append-before-persistence residue after integrity had failed.

For post-provider remediation, this is especially important: a provider action may already have happened, so a failed final lifecycle save must hide the candidate outcome while the execution-safety layer prevents replay.

### Exact changes made

#### Centralized non-CAS snapshot rollback in base `IncidentService`

Updated `runtime/incident_service.py`.

`_record_snapshot_transition(...)` now:
1. captures the previously authoritative in-process snapshot;
2. installs the candidate only for the duration of the attempted audit/checkpoint transition;
3. preserves the existing CAS-conflict path unchanged;
4. restores the previous snapshot on every other exception;
5. when checkpoint persistence is configured, marks audit/integrity state `failed`, causing subsequent lifecycle mutations to fail closed.

The base `audit_timeline(...)` now also rejects reads while audit integrity is `failed`, so append-before-persistence residue cannot be presented as committed operator history in non-anchored compositions.

Commit:
- `b22bc265927ce1962d2e1d239c4b4c81680fb49c` — centralize failed transition snapshot authority.

#### Added deterministic base and post-provider regressions

Added `runtime/tests/test_transition_failure_snapshot_authority.py`.

Coverage includes:
- failed re-investigation after one committed incident: previous snapshot and durable checkpoint remain authoritative, physical audit residue is retained, timeline fails closed, and further mutation is blocked;
- failed approval persistence: the uncommitted approval never becomes visible in memory or durable state;
- failed remediation outcome persistence after the provider action: previous approved/no-outcome state remains visible, durable outcome remains absent, the provider is called exactly once, execution uncertainty blocks replay, and the timeline fails closed.

Commit:
- `eb4726e6f6155540e9872e6ea19a5a5bec6f8890` — test base transition persistence failure authority.

### Checks / results

- GitHub compare from the prior handoff `9f36121ebbac1bed1da2c797822a1406a18b3160` through `eb4726e6f6155540e9872e6ea19a5a5bec6f8890` is exactly two commits ahead and touches only:
  - `runtime/incident_service.py`: +11/-2;
  - `runtime/tests/test_transition_failure_snapshot_authority.py`: +153/-0.
- Re-read the exact production diff after commit; no unrelated `incident_service.py` changes were introduced.
- Attempted a fresh local checkout before executable validation; the execution container still failed with `Could not resolve host: github.com`.
- Because checkout remains unavailable, the new unittest module and focused transition/execution-safety suites could not be executed in this run.
- No GitHub Actions workflow was created, modified, triggered, or rerun as a workaround.
- No GCP/IAM/Cloud Run, Grafana Cloud, Gemini provider, incident, remediation, or external audit resource was mutated.

No green repository-suite claim is made for this run.

### Decisions

1. Snapshot authority now depends on the complete lifecycle transition succeeding, not merely on avoiding CAS contention.
2. CAS conflicts remain distinct: they still set the explicit checkpoint-conflict flag and require durable reload rather than being collapsed into generic integrity failure.
3. Non-CAS failures in checkpoint-backed base services mark integrity failed and block further lifecycle mutation.
4. Failed-integrity timeline reads fail closed rather than falling back to raw durable events.
5. Post-provider persistence failure preserves execution-safety semantics: the candidate outcome is hidden and the provider action must never be replayed.
6. Preserve append-before-persistence residue for forensic reconstruction; do not rewrite or silently delete it.
7. Continue avoiding noisy CI solely to work around transient execution-environment DNS failure.

### Blockers / unknowns

- `runtime/tests/test_transition_failure_snapshot_authority.py` still needs execution from a real repository checkout.
- The anchored and base transition-authority suites should be run together to detect redundant/interaction regressions after centralization.
- Generic post-provider persistence failure now marks audit integrity failed while execution uncertainty is also set; the external status/API representation of these simultaneous barriers should be reviewed so operators receive one clear, actionable fail-closed state without weakening no-replay guarantees.
- The production anchored and base execution-safety suites still need a current executable run.
- The complete evidence-unavailable safety set still needs a current combined executable run.
- The focused Cloud Run audience/redirect/sentinel/bridge suites need a current executable run.
- The disposable private Cloud Run acceptance requires a private StageGuard test service, working ADC for a least-privilege invoker identity, and Docker.
- Playwright evidence-unavailable browser acceptance still needs execution with Chromium.
- Historical full-suite failures/errors have not yet been re-triaged; there is no full-suite green claim.

## Single best next step

**Review and harden the simultaneous `audit_integrity=failed` + post-provider `execution_uncertain` operator/API contract. Ensure a non-CAS failure after provider dispatch has one explicit externally visible state that communicates both “do not trust the failed lifecycle write” and “do not replay remediation,” while retaining the stable operation identity needed for reconciliation. Add API/status regressions, then run the base + anchored transition-authority and execution-safety suites together as soon as checkout execution is available.**

## Recent hardening retained

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

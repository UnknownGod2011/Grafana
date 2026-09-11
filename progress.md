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
- A losing optimistic-concurrency writer must not remain visible through `status()` as if its incident revision or approval were committed.
- The browser and HTTP API must not expose provider failure detail or turn evidence loss into actionable state.
- Private Cloud Run metrics requests must not follow redirects and must keep token audience/target boundaries explicit.
- Runtime metrics readiness requires an unambiguous StageGuard safety sentinel, not merely HTTP 200.

## Run log — 2026-09-12 — checkpoint-conflict snapshot authority

### Inspected at start

Read `progress.md` completely before deciding what to change. Then inspected:
- `runtime/incident_service.py`, especially `_record()`, `_save_checkpoint()`, `investigate()`, `approve()`, `status()`, and conflict reload behavior;
- `runtime/incident_checkpoint.py`, including `CheckpointConflictError`, checkpoint schema, and `CheckpointStore` semantics;
- `runtime/tests/test_evidence_unavailable_lifecycle.py` and `runtime/tests/test_api.py` for existing service fixtures and diagnosed telemetry values;
- the runtime tests inventory for existing checkpoint/audit/concurrency coverage.

A clean executable checkout was attempted with:

```bash
git clone --depth 1 https://github.com/UnknownGod2011/Grafana.git /tmp/stageguard
```

The execution container again failed with `Could not resolve host: github.com`. The connected GitHub integration itself was available for reads and writes, so implementation continued there without triggering CI.

### Finding

`IncidentService.investigate()` and `IncidentService.approve()` assigned their candidate `IncidentSnapshot` to `self._snapshot` before `_record()` attempted durable checkpoint persistence. `_record()` correctly treats checkpoint persistence as lifecycle authority and marks a `CheckpointConflictError` as conflicted, but the pre-assigned candidate remained visible through `status()` after the CAS loss.

That creates a split-brain presentation problem: the durable checkpoint winner can still represent the previous incident/approval state while the losing process temporarily exposes an uncommitted revision or approval in memory. The service blocks further lifecycle mutations until explicit reload, but read paths should not portray a losing transition as authoritative during that interval.

### Exact changes made

#### Non-authoritative loser snapshots

Updated `runtime/incident_service.py` with `_record_snapshot_transition(...)`.

The helper:
1. remembers the previous committed in-process snapshot;
2. temporarily installs the candidate only because checkpoint serialization needs the candidate state;
3. calls the existing append-before-CAS `_record()` path;
4. on `CheckpointConflictError`, restores the previous snapshot and re-raises;
5. on success, leaves the candidate published.

`investigate()` and `approve()` now use this helper. No checkpoint-store policy was duplicated, the existing explicit reload requirement remains intact, and append-before-CAS audit residue remains available for durable lineage selection.

Commit:
- `f97f2bb635ca8e0e0ca88d05a88f73cf4cc7d5c4` — keep conflicted lifecycle snapshots non-authoritative.

The commit diff was reviewed after writing. Functional changes are limited to the new transition helper and routing `investigate()` / `approve()` through it. Three explanatory comments in `_restore_audit_integrity()` were removed while replacing the full file through the GitHub contents API; behavior in those branches is unchanged. Restoring those comments is cleanup-only and not required for correctness.

#### Focused regression coverage

Added `runtime/tests/test_checkpoint_conflict_snapshot_authority.py`.

It uses a deterministic checkpoint store that keeps the previous durable winner and raises `CheckpointConflictError` on a selected save. It covers:

1. **losing re-investigation**
   - first investigation commits successfully;
   - second investigation loses CAS;
   - service enters `checkpoint_state == "conflicted"`;
   - `status()` still equals the first committed snapshot;
   - append-before-CAS loser audit residue exists in the raw audit sink but does not enter the authoritative in-process timeline;
   - further lifecycle mutation is blocked pending explicit reload;
   - `reload_checkpoint_after_conflict()` restores the durable winner and returns to `synchronized`.

2. **losing approval**
   - diagnosed investigation commits successfully;
   - approval loses CAS;
   - `status()` remains the pre-approval snapshot with `approval is None`;
   - durable winner also has no approval;
   - raw loser audit residue is present but not exposed as committed timeline state;
   - explicit reload keeps the unapproved durable winner authoritative.

Commit:
- `d95205e57645d5d1bef997ad7d496580ea425221` — test checkpoint conflict snapshot authority.

### Checks / results

- Reviewed the actual commit diff from GitHub after updating `incident_service.py`; no unintended executable changes beyond the conflict-authority implementation were present.
- Re-read the committed regression file from `main` after creation.
- Independently Python-compiled the new regression source prefix containing imports/classes/store definitions; syntax check passed.
- A real focused unittest run could not be started because the execution container cannot currently resolve `github.com` for checkout.
- No GitHub Actions workflow was created, modified, triggered, or rerun.
- No GCP/IAM/Cloud Run, Grafana Cloud, Gemini provider, incident, remediation, or external audit resource was mutated.

No green repository-suite claim is made for this run.

### Decisions

1. Fix the authority boundary in `IncidentService` rather than hiding conflicted state only in the HTTP layer; all callers should see the same semantics.
2. Preserve append-before-CAS audit behavior because loser residue is required for authenticated lineage selection in stores/readers that can enumerate branches.
3. Roll back only the candidate snapshot on `CheckpointConflictError`; the conflict flag remains authoritative and forces explicit reload before further lifecycle mutation.
4. Cover both investigation replacement and approval publication because an uncommitted approval is especially dangerous for an incident commander.
5. Do not alter execution/remediation conflict semantics in this change. Provider dispatch can have irreversible side effects and requires a separate review of the existing dispatching/anchored execution protocol rather than applying snapshot rollback mechanically.
6. Avoid CI solely to work around the transient execution-environment DNS failure.

### Blockers / unknowns

- `runtime/tests/test_checkpoint_conflict_snapshot_authority.py` still needs execution from a real repository checkout.
- The complete evidence-unavailable safety set still needs a current combined executable run.
- The focused Cloud Run audience/redirect/sentinel/bridge suites need a current executable run.
- The disposable private Cloud Run acceptance still requires a private StageGuard test service, working ADC for a least-privilege invoker identity, and Docker.
- Playwright evidence-unavailable browser acceptance still needs execution with Chromium.
- Historical full-suite failures/errors have not yet been re-triaged; there is no full-suite green claim.

## Single best next step

**Review the execution/remediation checkpoint protocol for the same authority hazard, specifically the interval between provider dispatch, `dispatching` persistence, outcome creation, and `remediation_completed` checkpoint commit. Add a focused regression proving that a checkpoint conflict cannot make a losing process re-dispatch an already-started remediation or expose an uncommitted outcome. Do not apply a generic rollback until the irreversible provider-side-effect semantics are understood.**

## Recent hardening retained

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

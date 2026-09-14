# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the read-only runtime evidence plane. The implemented vertical slice includes deterministic telemetry, Prometheus/Loki/Grafana, official Grafana MCP access, bounded investigation and diagnosis, optional Gemini briefing, exact-revision approval, remediation adapters, telemetry-verified recovery, authenticated lifecycle state, checkpoint/audit integrity, operator UI, Cloud Run deployment hardening, watchdog observability, authenticated private metrics bridging, evidence-unavailable abstention, fail-closed HTTP/operator handling, no-replay reconciliation for post-remediation persistence uncertainty, versioned metric/Loki onboarding activation, recovery-only Grafana rechecks after accepted remediation, a fixed-cardinality recovery lifecycle contract shared by lifecycle JSON/readiness/Prometheus/Grafana, and a browser cockpit that now consumes that server-derived recovery contract instead of independently deriving recovery state.

Detailed older run history remains in Git history; this file keeps the current invariants, validation baseline, latest run, blockers, and next step.

## Core invariants

- Grafana/MCP is read-only evidence access; infrastructure-write credentials remain isolated.
- Investigation and recovery accept only finite non-boolean numeric metric evidence; malformed samples become unavailable and can never prove diagnosis/recovery.
- Loki corroboration validates adapter envelopes, exact evidence windows, record budgets/shapes, scope, and event identity before corroborating a diagnosis.
- Gemini is advisory and cannot mutate diagnosis, approval, remediation, or recovery state; its context/JSON boundary rejects malformed or non-finite evidence.
- Required evidence unavailability prevents briefing, approval, and execution from becoming actionable.
- Approval is exact-revision-bound and single-use; remediation acceptance requires literal boolean `True`.
- Provider action success never counts as recovery; fresh Grafana telemetry must prove recovery.
- Once an accepted provider action has produced `recovery_unverified`, follow-up verification uses a recovery-only path that has no remediation client and therefore cannot replay the provider side effect.
- Durable `recovery_unverified` state survives restart and remains eligible only for recovery-only verification; restart must never reopen provider execution for the consumed approval.
- `recovered` is terminal for recovery recheck/provider execution and means fresh telemetry proved recovery.
- Durable checkpoint/audit failures fail closed; once provider dispatch may have occurred, persistence uncertainty blocks replay.
- Production remediation HTTP requests never follow redirects and do not redirect bearer/idempotency authority.
- Authentication/identity inputs are bounded and attacker-controlled credentials are bounded before comparison.
- Metric activation v2 pins the exact ordered eight-query profile contract; Loki activation v2 pins policy-owned LogQL/limit and bounded preflight evidence.
- The reference Grafana MCP dependency is pinned to `grafana/mcp-grafana:1.4.1`; read-only/tool-surface restrictions are regression-locked.
- Core remediation watchdog clocks are finite native numbers; invalid/backward active clocks fail readiness closed.
- Local cooperative audit-lock sidecars and local audit/checkpoint data files are symlink/hard-link/path-substitution hardened and owner-private.
- On POSIX/Cloud Run, checkpoint reads/writes and generic secure opens bind to one validated parent-directory descriptor; parent substitution cannot redirect state access.
- Local checkpoint parents must not be group- or world-writable, including sticky world-writable directories.
- Recovery observability is fixed-cardinality and provider-detail-free: it may expose only bounded lifecycle state, literal action acceptance, no-replay recheck eligibility, recovery verification, bounded sample count, and checkpoint-phase consistency. It must not export incident IDs, revisions, actors, queries, datasource identities, provider metadata, operation IDs, or remediation targets.
- A durable recovery outcome must agree with execution phase `resolved`; phase mismatch is exported explicitly, fails readiness closed, and has a dedicated critical Grafana alert.
- Grafana recovery panels query only fixed-cardinality recovery metric families; they do not introduce incident/revision/provider/query/target labels.
- The browser operator cockpit trusts the authenticated server-produced `recovery` contract for recovery labels and no-replay recheck eligibility. Missing, malformed, self-inconsistent, or checkpoint-inconsistent recovery contracts fail closed and disable lifecycle mutations rather than falling back to nested incident outcome interpretation.

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected platform-specific permission test skipped on Windows.
- Focused core/API/UI suite from the last executable repository run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating the latest hardening/recovery work.
- Historical official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`; pinned `1.4.1` still requires a live smoke.
- Current committed recovery/API/Grafana/operator regressions remain blocked from repository execution because this automation runner cannot resolve `github.com`; authenticated connector reads/writes work, but commits are not treated as passing tests.

## Run log — 2026-09-14 — server-derived operator recovery contract

### Inspected at start

Read this `progress.md` completely before selecting work. Inspected `runtime/operator_console.py`, `runtime/tests/test_operator_recovery_recheck.py`, `runtime/recovery_observability.py`, and the lifecycle/readiness/metrics wiring in `runtime/api.py`. Confirmed the server already emits one bounded `recovery` object containing `state`, `action_accepted`, `recheck_eligible`, `verified`, `sample_count`, and `checkpoint_phase_consistent`.

No unrelated repository, cloud resource, Grafana instance, Gemini endpoint, remediation provider, IAM binding, or GitHub Actions workflow was modified or triggered.

### Finding

The authenticated lifecycle API was already the authoritative recovery-state source, but the browser cockpit still derived recovery recheck eligibility and recovered/unverified labels from `current.outcome.status` and `current.outcome.action_result.accepted`. That duplicated lifecycle interpretation in the browser and meant a malformed or divergent server recovery contract could be ignored by the UI. The recovery card also rendered the full outcome object rather than the bounded provider-detail-free recovery view.

### Exact changes made

1. Added strict browser validation for the authenticated server-produced recovery contract. Recognized states are fixed to `none`, `approval_required`, `action_failed`, `recovery_unverified`, `recovered`, and `unknown`.
2. Required literal booleans for action acceptance, recheck eligibility, verification, and checkpoint consistency; required integer `sample_count` in the bounded 0..100 range.
3. Added cross-field validation: `verified` must exactly match `state === recovered`, and `recheck_eligible` must exactly match `state === recovery_unverified && action_accepted === true`.
4. Removed browser derivation of recheck eligibility from `current.outcome.status` / `current.outcome.action_result.accepted`; `recoveryRecheckAvailable()` now trusts only validated `data.recovery.recheck_eligible`.
5. Wired every lifecycle response through `render(data.incident, data.recovery, ...)` so refresh, investigate, execute, recheck, reload, and reconciliation all refresh the same server-derived recovery contract.
6. Added a fail-closed recovery contract safety block. Missing, malformed, self-inconsistent, or checkpoint-phase-inconsistent recovery data disables lifecycle mutation controls and surfaces an explicit operator safety message instead of inferring state in the browser.
7. Changed the operator proof panel to render `RECOVERED ✓` and `RECHECK ONLY` from the server recovery contract rather than nested outcome status.
8. Changed the recovery card to display only the bounded recovery contract, not the full remediation outcome/provider result structure.
9. Preserved the existing no-provider-replay path and all existing checkpoint, audit-integrity, and composite safety interlocks.
10. Extended `runtime/tests/test_operator_recovery_recheck.py` to regression-lock server-contract use, strict type/cross-field validation, fail-closed malformed/missing behavior, cold-restart `recovery_unverified` recheck-only labeling, terminal `recovered` labeling, and removal of the old outcome-derived eligibility checks.
11. Compared the functional delta against the previous progress head; exactly two functional files changed before this progress update.

Commits:
- `d412406bc28ac5a949c5de3a201991a6bf7421b4` — Trust server-derived recovery contract in operator cockpit
- `04688e4f2fad65b69c2290ba637e52ae94e193ad` — Lock server-derived recovery contract in operator UI

### Checks / results

- Authenticated GitHub connector reads/writes succeeded on `UnknownGod2011/Grafana` `main`.
- Commit comparison from `a57123a96cc14fc7511e9988e8cf1b642ef0f71e` through `04688e4f2fad65b69c2290ba637e52ae94e193ad` is `ahead` by two commits and reports exactly:
  - `runtime/operator_console.py` (+11/-9)
  - `runtime/tests/test_operator_recovery_recheck.py` (+28/-4)
- A fresh shallow clone was attempted before editing and still failed before checkout with `Could not resolve host: github.com`.
- Because executable checkout remains unavailable in this runner, the updated Python/embedded-JavaScript tests were not executed here and this run does not claim them green.
- No GitHub Actions workflow was triggered merely to bypass the runner DNS failure.

### Decisions

1. The authenticated lifecycle API is the single recovery-state authority; the browser should present and enforce it, not reconstruct it.
2. Recovery contract corruption or omission is a safety failure, not a compatibility condition. Operator mutation controls therefore fail closed.
3. Cross-field validation belongs in the browser too because the UI is a safety surface: a contradictory object such as `state=recovered, verified=false` must not silently produce actionable controls.
4. `checkpoint_phase_consistent=false` is treated as a lifecycle block in the cockpit, matching `/readyz` and Grafana alert semantics.
5. The recovery card intentionally shows only the bounded recovery view, reducing accidental exposure of remediation/provider metadata in the browser.
6. Existing provider execution remains separately guarded by the consumed approval/outcome model; this change does not create a new execution path.

### Blockers / unknowns

- The updated operator recovery regression still requires a current executable repository checkout.
- Recent audit/checkpoint/retention/recovery/Grafana regressions still require consolidated execution.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- The real disposable private Cloud Run acceptance still requires a private StageGuard service, least-privilege ADC invoker identity, and Docker.
- Historical full-suite failures/errors remain untriaged; there is still no full-suite green claim.

## Single best next step

**Add an executable browser-level/operator-console test harness (without external paid services) that feeds representative authenticated lifecycle payloads into the embedded cockpit JavaScript and proves controls for `none`, malformed recovery, `recovery_unverified`, and `recovered` states. This should validate actual DOM/button behavior rather than only source-string assertions, and should run locally without Grafana/Gemini/provider credentials.**

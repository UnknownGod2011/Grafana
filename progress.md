# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the read-only runtime evidence plane. The implemented vertical slice includes deterministic telemetry, Prometheus/Loki/Grafana, official Grafana MCP access, bounded investigation and diagnosis, optional Gemini briefing, exact-revision approval, remediation adapters, telemetry-verified recovery, authenticated lifecycle state, checkpoint/audit integrity, operator UI, Cloud Run deployment hardening, watchdog observability, authenticated private metrics bridging, evidence-unavailable abstention, fail-closed HTTP/operator handling, no-replay reconciliation for post-remediation persistence uncertainty, versioned metric/Loki onboarding activation, recovery-only Grafana rechecks after an accepted remediation whose first verification window remains unverified, and one fixed-cardinality recovery lifecycle observability contract shared by lifecycle JSON, readiness diagnostics, and Prometheus metrics.

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
- A durable recovery outcome must agree with execution phase `resolved`; phase mismatch is exported explicitly and fails readiness closed.

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected platform-specific permission test skipped on Windows.
- Focused core/API/UI suite from the last executable repository run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating the latest hardening/recovery work.
- Historical official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`; pinned `1.4.1` still requires a live smoke.
- Current committed recovery/API regressions remain blocked from repository execution because this automation runner cannot resolve `github.com`; authenticated connector reads/writes work, but commits are not treated as passing tests.

## Run log — 2026-09-14 — coherent recovery observability across API/readiness/metrics

### Inspected at start

Read this `progress.md` completely before selecting work. Inspected `runtime/api.py`, `runtime/recovery_observability.py`, `runtime/tests/test_api_recovery_recheck.py`, `runtime/tests/test_anchored_recovery_recheck.py`, `runtime/tests/test_recovery_recheck_restart.py`, `runtime/tests/test_readiness_api.py`, `runtime/tests/test_operator_recovery_recheck.py`, and the relevant `IncidentService.recheck_recovery()` state guard. No unrelated repository, cloud resource, Grafana instance, Gemini endpoint, remediation provider, IAM binding, or GitHub Actions workflow was modified or triggered.

### Finding

The reusable recovery-observability contract existed, but `runtime/api.py` still independently exposed lifecycle/readiness/Prometheus state without consuming it. As a result, an operator could see an incident outcome while dashboards/readiness had no first-class bounded recovery state, and there was no regression proving cold-restored `recovery_unverified` produced the same no-replay semantics across those surfaces.

### Exact changes made

1. Wired `recovery_observability()` into `_lifecycle_view()` and added a top-level authenticated `recovery` object alongside the incident snapshot.
2. The lifecycle recovery object exposes only bounded fields: `state`, `action_accepted`, `recheck_eligible`, `verified`, `sample_count`, and `checkpoint_phase_consistent`.
3. Wired the same derivation into `_service_readiness()` with bounded diagnostics: `recovery_state`, `recovery_recheck_eligible`, `recovery_verified`, and `recovery_checkpoint_phase`.
4. Made checkpoint/recovery phase inconsistency fail readiness closed without making ordinary accepted `recovery_unverified` unhealthy; an operator can therefore remain service-ready while being explicitly told that only a recovery recheck is allowed.
5. Wired `prometheus_recovery_metrics()` into `_service_metrics()` so `/metrics` now exports the same fixed-cardinality recovery contract used by the lifecycle/readiness views.
6. Extended the `/readyz` redacted exception fallback with bounded recovery diagnostics (`unknown`, non-eligible, non-verified, inconsistent) rather than omitting the recovery dimension during failures.
7. Extended `runtime/tests/test_api_recovery_recheck.py` so normal HTTP lifecycle responses prove the transition from `none` -> accepted `recovery_unverified`/recheck-eligible -> `recovered`/verified, while provider call count remains one.
8. Extended `runtime/tests/test_recovery_recheck_restart.py` so a cold-restored accepted `recovery_unverified` state is checked through lifecycle JSON, readiness diagnostics, and Prometheus metrics; the metrics test explicitly rejects incident ID/revision leakage.
9. The restart regression then performs the recovery-only recheck with a remediation adapter that raises if called, verifies the resulting `recovered` state is terminal/non-recheck-eligible, and verifies subsequent recovery recheck/provider execution attempts remain blocked.
10. Compared the complete delta against the previous progress head: only `runtime/api.py`, `runtime/tests/test_api_recovery_recheck.py`, and `runtime/tests/test_recovery_recheck_restart.py` changed before this progress update.

Commits:
- `575364acbc9faf6040f507a8ff0e3072d34ab558` — Wire recovery observability into API surfaces
- `6b0d2359b269ace6580a6b3ad93ebe080e6bcd73` — Cover recovery observability across cold restart
- `bf0be7d87d5ae66226bb8a41717f9459674e8c65` — Fix terminal recovery regression assertion
- `7bab1493ad4e2162aeae6e7cd7eb00cb9a87d9e7` — Assert recovery observability in lifecycle responses

### Checks / results

- Authenticated GitHub connector reads/writes succeeded on `UnknownGod2011/Grafana` `main`.
- Commit comparison from `3bb35d61b5f4ae9c66c6ca7a01a55068f546838a` through `7bab1493ad4e2162aeae6e7cd7eb00cb9a87d9e7` is `ahead` by four commits and reports exactly three modified files: `runtime/api.py` (+24/-2), `runtime/tests/test_api_recovery_recheck.py` (+14), and `runtime/tests/test_recovery_recheck_restart.py` (+45/-1).
- The touched production file was re-read after commit and the recovery import/lifecycle/readiness wiring is present.
- `IncidentService.recheck_recovery()` was re-inspected after writing the terminal regression; its actual guard message is `recovery recheck is only allowed while recovery remains unverified`, and the test assertion was corrected to match the production contract rather than guessing the wording.
- Focused executable command attempted: `PYTHONPATH=runtime python -m unittest runtime.tests.test_recovery_observability runtime.tests.test_recovery_recheck_restart runtime.tests.test_api_recovery_recheck runtime.tests.test_readiness_api` after a fresh shallow clone.
- Execution could not begin because the runner still fails at checkout with `Could not resolve host: github.com`. No GitHub Actions workflow was triggered merely to bypass that transient DNS failure, and this run does not claim the committed tests green.

### Decisions

1. `recovery_unverified` is an operator lifecycle condition, not by itself a service-readiness failure; readiness stays governed by evidence-plane/safety health while explicitly exposing recheck eligibility.
2. A recovery outcome whose durable execution phase is not `resolved` is an integrity inconsistency and therefore fails readiness closed.
3. Lifecycle JSON, readiness, and Prometheus must derive recovery state from the same helper instead of duplicating status interpretation.
4. Recovery Prometheus metrics remain strictly fixed-cardinality; incident/revision values are regression-checked not to appear in the rendered recovery surface.
5. Cold restart must preserve no-replay semantics. Restored `recovery_unverified` may query Grafana only; restored/rechecked `recovered` cannot re-enter either recovery recheck or provider execution.
6. No noisy CI run is justified while direct repository execution is blocked by runner DNS and the authenticated connector remains sufficient for source-level progress.

### Blockers / unknowns

- The newly extended recovery/API unittest set still requires a current executable repository checkout.
- Recent audit/checkpoint/retention/recovery regressions also still require consolidated execution.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- The real disposable private Cloud Run acceptance still requires a private StageGuard service, least-privilege ADC invoker identity, and Docker.
- Historical full-suite failures/errors remain untriaged; there is still no full-suite green claim.

## Single best next step

**Make the operator cockpit and Grafana runtime views consume the new server-derived recovery contract directly: replace duplicate browser-side recovery eligibility derivation with `data.recovery`, add recovery state/recheck/phase-consistency panels or alert rules to the StageGuard Grafana dashboard using the new fixed-cardinality metrics, and add regressions proving `recovery_unverified` is visibly recheck-only while `recovered` is terminal after cold restart.**

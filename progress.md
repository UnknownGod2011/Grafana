# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the read-only runtime evidence plane. The implemented vertical slice includes deterministic telemetry, Prometheus/Loki/Grafana, official Grafana MCP access, bounded investigation and diagnosis, optional Gemini briefing, exact-revision approval, remediation adapters, telemetry-verified recovery, authenticated lifecycle state, checkpoint/audit integrity, operator UI, Cloud Run deployment hardening, watchdog observability, authenticated private metrics bridging, evidence-unavailable abstention, fail-closed HTTP/operator handling, no-replay reconciliation for post-remediation persistence uncertainty, versioned metric/Loki onboarding activation, recovery-only Grafana rechecks after an accepted remediation whose first verification window remains unverified, one fixed-cardinality recovery lifecycle observability contract shared by lifecycle JSON/readiness/Prometheus, and first-class Grafana recovery panels/alerts for that same contract.

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
- A durable recovery outcome must agree with execution phase `resolved`; phase mismatch is exported explicitly, fails readiness closed, and now has a dedicated critical Grafana alert.
- Grafana recovery panels query only the fixed-cardinality recovery metric families; they must not introduce incident/revision/provider/query/target labels.

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected platform-specific permission test skipped on Windows.
- Focused core/API/UI suite from the last executable repository run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating the latest hardening/recovery work.
- Historical official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`; pinned `1.4.1` still requires a live smoke.
- Current committed recovery/API/Grafana regressions remain blocked from repository execution because this automation runner cannot resolve `github.com`; authenticated connector reads/writes work, but commits are not treated as passing tests.

## Run log — 2026-09-14 — Grafana recovery lifecycle observability

### Inspected at start

Read this `progress.md` completely before selecting work. Inspected the repository tree, `runtime/operator_console.py`, `runtime/recovery_observability.py`, `runtime/grafana/dashboards/stageguard-runtime.json`, `runtime/grafana/provisioning/alerting/stageguard-watchdog.yml`, `runtime/tests/test_operator_recovery_recheck.py`, and `runtime/tests/test_grafana_runtime_observability.py`. No unrelated repository, cloud resource, Grafana instance, Gemini endpoint, remediation provider, IAM binding, or GitHub Actions workflow was modified or triggered.

### Finding

The server-side recovery contract had already been wired into lifecycle JSON, readiness, and Prometheus, but the Grafana runtime dashboard still showed only remediation watchdog state. Operators therefore could not see whether recovery was telemetry-verified, whether only the no-replay recovery recheck path was eligible, or whether durable recovery state disagreed with the execution checkpoint phase. A checkpoint-phase mismatch failed `/readyz` closed but had no dedicated Grafana alert.

The browser cockpit still derives recovery recheck eligibility from nested incident outcome fields instead of `data.recovery`; that remains an open UI consistency gap and is intentionally recorded below rather than hidden.

### Exact changes made

1. Added a `Recovery verification` Grafana stat panel backed by `stageguard_recovery_verified`.
2. Added a `Recovery recheck eligibility` stat panel backed by `stageguard_recovery_recheck_eligible`, explicitly described as the no-provider-replay path.
3. Added a `Recovery checkpoint consistency` stat panel backed by `stageguard_recovery_checkpoint_phase_consistent`, with fail-closed semantics visible to operators.
4. Added a bounded `Recovery evidence samples` stat panel backed by `stageguard_recovery_sample_count` and documented that it carries no incident/provider/query/target/revision labels.
5. Added the `recovery` dashboard tag and advanced the dashboard version from 3 to 4.
6. Added a critical provisioned alert `stageguard-recovery-checkpoint-inconsistent` that fires when the consistency gauge remains below 0.5 for 10 seconds and binds directly to dashboard panel 9.
7. Kept missing-data semantics distinct from actual inconsistency: the new integrity alert uses `noDataState: NoData`, not `Alerting`, so a scrape outage is handled by the existing scrape/freshness alerts rather than falsely asserting checkpoint corruption.
8. Added explicit no-replay guidance to the new critical alert description.
9. Extended `runtime/tests/test_grafana_runtime_observability.py` to lock the four recovery metric queries, panel identities/titles, dashboard recovery tag, no-high-cardinality-selector rule, and critical checkpoint-consistency alert semantics.
10. Compared the complete functional delta against the previous progress head; exactly three files changed before this progress update.

Commits:
- `8c4c23d3114f42158f4229b2452c689c07986735` — Add recovery lifecycle panels to Grafana runtime dashboard
- `2c9bdfc15802270f24b97e48cec19101d748e9c4` — Alert on recovery checkpoint inconsistency
- `ecf6c0ebde1e2b44d9866d60ed3816b1fb45997f` — Lock recovery lifecycle Grafana observability

### Checks / results

- Authenticated GitHub connector reads/writes succeeded on `UnknownGod2011/Grafana` `main`.
- Commit comparison from `2205e2bec3ad0f5ed4e0f1697e0f605373401f21` through `ecf6c0ebde1e2b44d9866d60ed3816b1fb45997f` is `ahead` by three commits and reports exactly:
  - `runtime/grafana/dashboards/stageguard-runtime.json` (+46/-2)
  - `runtime/grafana/provisioning/alerting/stageguard-watchdog.yml` (+55)
  - `runtime/tests/test_grafana_runtime_observability.py` (+63)
- A fresh shallow clone plus `PYTHONPATH=runtime python -m unittest runtime.tests.test_grafana_runtime_observability` was attempted.
- Execution could not begin because the runner still fails checkout with `Could not resolve host: github.com`.
- No GitHub Actions workflow was triggered merely to bypass the transient DNS failure, and this run does not claim the committed tests green.

### Decisions

1. Recovery/checkpoint inconsistency is an integrity fault and deserves its own critical Grafana signal because it already withdraws API readiness.
2. Missing metrics and a proven zero-valued consistency gauge are different conditions; scrape/freshness alerts own transport absence while the new alert owns actual lifecycle inconsistency.
3. Recovery dashboard queries remain direct fixed-cardinality metric names with no user-controlled or incident-specific selectors.
4. `recovery_unverified` remains a normal operator lifecycle condition rather than a service outage; its dashboard signal is informative (`RECHECK ONLY`) and does not alert by itself.
5. No provider-specific data, incident IDs, evidence revisions, actor identities, datasource IDs, PromQL payloads, targets, or operation IDs were added to Grafana recovery panels or alert labels.
6. The existing browser cockpit should be changed next to trust the server-derived `data.recovery` object rather than independently deriving no-replay eligibility from nested outcome fields.

### Blockers / unknowns

- The updated Grafana observability unittest still requires a current executable repository checkout.
- The browser cockpit still duplicates recovery eligibility/state interpretation and has not yet been migrated to `data.recovery`.
- Recent audit/checkpoint/retention/recovery regressions still require consolidated execution.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- The real disposable private Cloud Run acceptance still requires a private StageGuard service, least-privilege ADC invoker identity, and Docker.
- Historical full-suite failures/errors remain untriaged; there is still no full-suite green claim.

## Single best next step

**Remove the remaining browser-side recovery-state duplication: make the operator cockpit use the authenticated server-derived `data.recovery` contract for recheck eligibility, recovered/unverified labels, and terminal-state controls; fail closed on malformed/missing recovery fields; then add cold-restart/operator regressions proving restored `recovery_unverified` is visibly recheck-only and restored `recovered` is terminal without reopening provider execution.**

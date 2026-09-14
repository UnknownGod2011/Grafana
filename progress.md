# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the read-only runtime evidence plane. The implemented vertical slice includes deterministic telemetry, Prometheus/Loki/Grafana, official Grafana MCP access, bounded investigation and diagnosis, optional Gemini briefing, exact-revision approval, remediation adapters, telemetry-verified recovery, authenticated lifecycle state, checkpoint/audit integrity, operator UI, Cloud Run deployment hardening, watchdog observability, authenticated private metrics bridging, evidence-unavailable abstention, fail-closed HTTP/operator handling, no-replay reconciliation for post-remediation persistence uncertainty, versioned metric/Loki onboarding activation, recovery-only Grafana rechecks after an accepted remediation whose first verification window remains unverified, and a reusable fixed-cardinality recovery lifecycle observability contract.

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
- Durable `recovery_unverified` state is intended to survive restart and remain eligible only for the recovery-only verification path; restart must never reopen provider execution for the consumed approval.
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

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected platform-specific permission test skipped on Windows.
- Focused core/API/UI suite from the last executable repository run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating the latest hardening/recovery work.
- Historical official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`; pinned `1.4.1` still requires a live smoke.
- Recent hardening/recovery regressions remain blocked from full repository execution because this automation runner cannot resolve `github.com`; connector reads/writes work, but commits are not treated as passing repository tests.

## Run log — 2026-09-14 — recovery lifecycle observability contract

### Inspected at start

Read this `progress.md` completely before selecting work. Inspected `runtime/readiness.py`, `runtime/api.py`, `runtime/incident_checkpoint.py`, `runtime/incident_service.py`, `runtime/remediation.py`, the current recovery-recheck regressions, and the production Cloud Run entrypoint. No unrelated repository, cloud resource, Grafana instance, Gemini endpoint, remediation provider, IAM binding, or GitHub Actions workflow was modified or triggered.

### Finding

The recovery-only lifecycle is durable and no-replay safe, but the existing Prometheus surface currently exports evidence-plane readiness, checkpoint conflict state, execution uncertainty/watchdog phase, reconciliation reason, audit integrity/policy, and composite lifecycle safety without a dedicated recovery outcome contract. That makes `recovered` versus accepted `recovery_unverified` less explicit for dashboards/alerts than the rest of the production lifecycle.

The safest implementation boundary is fixed-cardinality derivation from the already-sanitized durable incident snapshot plus durable execution phase. Recovery telemetry must not create labels from incident IDs, revisions, actors, provider details, datasource UIDs, queries, operation IDs, or targets.

### Exact changes made

1. Added `runtime/recovery_observability.py` with a reusable `RecoveryObservability` value object and fixed state set: `none`, `approval_required`, `action_failed`, `recovery_unverified`, `recovered`, and `unknown`.
2. Added `recovery_observability(snapshot, execution_phase)` to derive only bounded, provider-detail-free state from durable lifecycle data.
3. Added explicit `recheck_eligible` semantics: it is true only for `recovery_unverified` with literal `action_result.accepted is True`; a custom/unknown provider status cannot enable a recheck.
4. Added explicit `verified` semantics: only the exact `recovered` state is considered telemetry-proven recovery.
5. Added `checkpoint_phase_consistent` so any durable outcome is expected to agree with `execution_phase == resolved`; pre-outcome lifecycle phases remain valid for the `none` recovery state.
6. Added defensive bounded recovery sample counting. Non-tuple/injected sample shapes produce `0`, and count is capped at `100` even though normal recovery verification already has much tighter internal bounds.
7. Added `prometheus_recovery_metrics()` with one-hot fixed-cardinality recovery state plus action acceptance, no-replay recheck eligibility, recovery verification, sample count, and checkpoint-phase consistency gauges.
8. Added `runtime/tests/test_recovery_observability.py` covering no-outcome state, accepted unverified eligibility, recovered state, non-accepted unverified denial, unknown-status fail-closed mapping, checkpoint phase mismatch, bounded sample count, one-hot metric state, and absence of high-cardinality/provider-detail markers.
9. Compared the delta against the previous `main` head; only the new recovery observability module and its regression file changed before this progress update.

Commits:
- `ee8d2c48d67bc16953b784c2ed9ed4a2c16ba616` — Add fixed-cardinality recovery lifecycle observability
- `ecd8edb67dd1331c636a27cd5fe4384d0895391a` — Fix recovery observability module import
- `7e8a056b2dfba13b7fab02c7fd6af280e3880c42` — Add recovery observability regressions

### Checks / results

- Authenticated GitHub connector reads/writes succeeded on `UnknownGod2011/Grafana` `main`.
- The runner again failed before checkout with `Could not resolve host: github.com`; no GitHub Actions workflow was triggered merely to bypass that DNS failure.
- Because a repository checkout was unavailable, the new committed unittest module is not claimed green.
- The new recovery-observability implementation was independently reproduced in the local runner and passed `python -m py_compile` plus a focused smoke proving accepted `recovery_unverified` becomes recheck-eligible, remains unverified, preserves bounded sample count, and renders the expected fixed-cardinality Prometheus gauges.
- Commit comparison from `d832d6c990f6eb4754c5a319a041d1af305ffbf5` through `7e8a056b2dfba13b7fab02c7fd6af280e3880c42` showed only `runtime/recovery_observability.py` and `runtime/tests/test_recovery_observability.py` changed.

### Decisions

1. Recovery dashboards/alerts should consume fixed-cardinality lifecycle state rather than incident-specific labels.
2. `recovery_unverified` with literal provider acceptance means "safe to re-query Grafana only"; it never implies permission to replay remediation.
3. `recovered` is the only recovery-verified state.
4. Unknown/custom outcome strings fail closed into one bounded `unknown` metric bucket.
5. Checkpoint execution phase consistency is worth exporting independently so durable-state corruption/regression can be alerted on without leaking checkpoint contents.
6. This run intentionally introduced the reusable contract first rather than duplicating recovery-state derivation directly inside `api.py`; the next change should wire this exact helper into the existing service metrics/lifecycle view and restart UI path.

### Blockers / unknowns

- The new recovery-observability unittest still requires a current executable repository checkout.
- Recent audit/checkpoint/retention/recovery-recheck regressions also still require consolidated execution.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- The real disposable private Cloud Run acceptance still requires a private StageGuard service, least-privilege ADC invoker identity, and Docker.
- Historical full-suite failures/errors remain untriaged; there is still no full-suite green claim.

## Single best next step

**Wire `recovery_observability()` / `prometheus_recovery_metrics()` into `runtime/api.py` so `/metrics`, `/readyz` diagnostics, and the authenticated lifecycle view expose one coherent recovery state; then add a cold-restart API/operator regression proving restored accepted `recovery_unverified` renders as recheck-eligible while restored `recovered` renders as verified and never reopens provider execution.**

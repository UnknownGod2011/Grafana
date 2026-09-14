# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the read-only runtime evidence plane. The implemented vertical slice includes deterministic telemetry, Prometheus/Loki/Grafana, official Grafana MCP access, bounded investigation and diagnosis, optional Gemini briefing, exact-revision approval, remediation adapters, telemetry-verified recovery, authenticated lifecycle state, checkpoint/audit integrity, operator UI, Cloud Run deployment hardening, watchdog observability, authenticated private metrics bridging, evidence-unavailable abstention, fail-closed HTTP/operator handling, no-replay reconciliation for post-remediation persistence uncertainty, versioned metric/Loki onboarding activation, and recovery-only Grafana rechecks after an accepted remediation whose first verification window remains unverified.

Detailed older run history remains in Git history; this file keeps the current invariants, validation baseline, latest run, blockers, and next step.

## Core invariants

- Grafana/MCP is read-only evidence access; infrastructure-write credentials remain isolated.
- Investigation and recovery accept only finite non-boolean numeric metric evidence; malformed samples become unavailable and can never prove diagnosis/recovery.
- Loki corroboration validates adapter envelopes, exact evidence windows, record budgets/shapes, scope, and event identity before corroborating a diagnosis.
- Gemini is advisory and cannot mutate diagnosis, approval, remediation, or recovery state; its context/JSON boundary rejects malformed or non-finite evidence.
- Required evidence unavailability prevents briefing, approval, and execution from becoming actionable.
- Approval is exact-revision-bound and single-use; remediation acceptance requires literal boolean `True`.
- Provider action success never counts as recovery; fresh Grafana telemetry must prove recovery.
- Once an accepted provider action has produced `recovery_unverified`, follow-up verification uses a recovery-only path that has no remediation client and therefore cannot replay the provider side effect. Rechecks require the already-consumed accepted outcome, preserve the same incident/revision/approval, and append a bounded `recovery_rechecked` audit event with `provider_replayed=false`.
- Production recovery-only polling runs outside the lifecycle lock so status/readiness stay responsive; competing lifecycle mutations remain blocked while verification is active. A Grafana/query failure during this read-only recheck does not manufacture provider-execution uncertainty.
- Durable `recovery_unverified` state is intended to survive restart and remain eligible only for the recovery-only verification path; restart must never reopen provider execution for the consumed approval.
- Durable checkpoint/audit failures fail closed; once provider dispatch may have occurred, persistence uncertainty blocks replay.
- Production remediation HTTP requests never follow redirects and do not redirect bearer/idempotency authority.
- Authentication/identity inputs are bounded and attacker-controlled credentials are bounded before comparison.
- Metric activation v2 pins the exact ordered eight-query profile contract; Loki activation v2 pins policy-owned LogQL/limit and bounded preflight evidence.
- The reference Grafana MCP dependency is pinned to `grafana/mcp-grafana:1.4.1`; read-only/tool-surface restrictions are regression-locked.
- Core remediation watchdog clocks are finite native numbers; invalid/backward active clocks fail readiness closed.
- Local cooperative audit-lock sidecars must be owner-only, single-link regular files, may not be symbolic links, and the opened descriptor must match the exact file identity still visible at the sidecar path.
- Secure local audit data descriptors must name a single-link regular file that still matches the visible pathname; symbolic links, hard-link aliases, and path substitution fail closed.
- Base and anchored local JSONL audit create/read/append paths use the shared secure descriptor primitive under the cooperative audit lock.
- Retention planning/execution uses the shared secure descriptor primitive, revalidates descriptor/path identity immediately before destructive pathname replacement, and builds recovery backups from the already-open authenticated source descriptor.
- Both unsigned and HMAC-signed local JSON checkpoint stores use the dedicated descriptor-bound checkpoint primitive; symlinks, hard-link aliases, post-open file substitution, unsafe truncation, and post-replace pathname chmod races are rejected or avoided.
- On POSIX/Cloud Run, checkpoint atomic writes bind temporary creation and final replacement to one validated parent-directory descriptor; parent-path substitution cannot redirect the write into a substituted directory.
- On POSIX/Cloud Run, checkpoint bounded reads bind the basename open and subsequent file-identity checks to one validated parent-directory descriptor; parent-path substitution cannot redirect a read into a substituted directory.
- On POSIX/Cloud Run, the generic secure checkpoint opener also binds existing-file opens and `O_CREAT` creation to one validated parent-directory descriptor before returning a file descriptor.
- Local checkpoint parents must not be group- or world-writable, including sticky world-writable directories. Directory ownership equality is deliberately not required so container/volume ownership models can remain compatible when namespace permissions are otherwise private.
- A genuinely absent local checkpoint preserves normal empty-store semantics (`None`) without reintroducing a separate `exists()`/open race.

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected platform-specific permission test skipped on Windows.
- Focused core/API/UI suite from the last executable repository run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating the latest hardening and recovery-recheck work.
- Historical official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`; pinned `1.4.1` still requires a live smoke.
- Recent hardening and recovery-recheck regressions remain blocked from full repository execution because this automation runner cannot resolve `github.com`; connector reads/writes work, but commits are not treated as passing repository tests.

## Run log — 2026-09-14 — no-replay recovery-only verification

### Inspected at start

Read this `progress.md` completely before selecting work. Inspected the current repository/runtime tree and then traced the production operator workflow through `runtime/incident_service.py`, `runtime/remediation.py`, `runtime/api.py`, `runtime/operator_console.py`, `runtime/execution_safety.py`, `runtime/anchored_execution_safety.py`, the existing incident/API/operator tests, and `OPERATOR_CONSOLE.md`. Also inspected the Cloud Logging audit envelope to confirm the new bounded audit payload remains compatible. No unrelated repository, cloud resource, Grafana instance, Gemini endpoint, remediation provider, IAM binding, or GitHub Actions workflow was modified or triggered.

### Finding

The main operator path had a real dead end after a successful provider mutation: `remediate_and_verify()` can correctly return `recovery_unverified` when the action was accepted but the bounded Grafana verification window did not establish the required healthy streak. The approval is then consumed, so replaying `/v1/execute` is correctly forbidden, but there was no lifecycle/API/UI operation that could safely collect fresh recovery evidence later. Operators were forced toward a fresh investigation or ad-hoc handling even though the safest next operation is simply to query Grafana again without touching the provider.

A second production concern appeared while implementing the fix: the base service can hold its lock while polling, but the production anchored execution-safe runtime intentionally keeps slow provider/Grafana I/O outside the lifecycle lock so authenticated reads remain responsive. A recovery-only recheck therefore needed the same nonblocking production treatment without falsely representing the read-only operation as another provider dispatch.

### Exact changes made

1. Added `verify_recovery()` in `runtime/remediation.py`. It receives an already-sanitized accepted `ActionResult` plus the metric client, uses only the pinned recovery queries, requires finite non-boolean samples, requires the existing consecutive healthy streak, and has no remediation-client parameter or provider-write code path.
2. Refactored `remediate_and_verify()` so the provider action is still dispatched once and, only after literal acceptance, delegates bounded telemetry verification to the shared `verify_recovery()` path.
3. Added `IncidentService.recheck_recovery()`. It is allowed only for a completed `recovery_unverified` outcome whose stored action result is literally accepted. It preserves incident ID, evidence revision, report, and consumed approval, promotes only the new recovery outcome, and records `recovery_rechecked` with revision/status/sample count plus `provider_replayed=false`.
4. Added authenticated `POST /v1/recovery/recheck`. The endpoint accepts an empty JSON object only, derives actor identity from the configured identity provider, and returns the normal bounded lifecycle view.
5. Added a same-origin **Recheck recovery only** operator control. It appears only for `recovery_unverified + accepted=true`, remains behind all existing composite lifecycle/audit/checkpoint safety interlocks, explicitly tells the operator the provider will not be called again, and renders the resulting recovery state from fresh Grafana evidence.
6. Hardened the production `AnchoredExecutionSafeIncidentService.recheck_recovery()` path so potentially slow Grafana polling runs outside `_lock`, while `_execution_in_flight` blocks competing lifecycle mutations and keeps watchdog observability active. The UI-facing phase remains `resolved` during recovery-only verification rather than falsely claiming a provider `dispatching` phase.
7. Recovery-only telemetry/query failures clear the active watchdog and preserve the prior authoritative `recovery_unverified` snapshot; they do not set provider-execution uncertainty because this operation performs no provider side effect.
8. Added focused service regressions in `runtime/tests/test_recovery_recheck.py` proving recovery can later become verified, repeated unverified checks do not replay, invalid lifecycle states are rejected, and provider call count stays exactly one.
9. Added production concurrency regressions in `runtime/tests/test_anchored_recovery_recheck.py` proving operator reads remain responsive while recovery polling is blocked, competing mutations fail closed, the activity is not reported as provider dispatch, provider call count stays one, and a Grafana failure does not create execution uncertainty.
10. Added `runtime/tests/test_api_recovery_recheck.py` covering authentication, empty-body policy, end-to-end API transition, audit actor provenance, and provider non-replay.
11. Added `runtime/tests/test_operator_recovery_recheck.py` covering the new UI control, accepted/unverified gating, composite safety blocking, same-origin endpoint use, explicit no-replay messaging, and continued absence of provider/credential/browser-persistence markers.
12. Added `runtime/tests/test_recovery_recheck_restart.py` to lock the durable contract: an accepted `recovery_unverified` outcome is restored after restart and can be promoted to `recovered` through fresh Grafana evidence while the restarted remediation adapter is deliberately incapable of being called.
13. Updated `OPERATOR_CONSOLE.md` with the recovery-only workflow, endpoint contract, audit semantics, production nonblocking behavior, and test coverage.
14. Compared the run against the previous `main` head to verify that changes are confined to the intended remediation/lifecycle/API/operator/docs/tests surface. Cloud audit validation was reviewed and already accepts the new bounded scalar payload without exposing provider detail.

Commits:
- `a9622f788c2c946804a19f06e25f21cb634b949b` — Add recovery-only Grafana verification path
- `7771bcb641e49e0b65d2494040eeb33894fd02f0` — Add no-replay recovery recheck lifecycle
- `e48ab8dea93d55e43656bbcf25ec1bb9e47b85af` — Expose safe recovery-only recheck endpoint
- `9d9362f692de240b17d436b8c76c92690ef8268d` — Add no-replay recovery recheck regressions
- `2f62a55a05c802aa10f7e6c9008708c6953c2eab` — Add recovery-only recheck operator control
- `e2b513b701a83cda73268a9ad0c432bc285e3e11` — Keep recovery rechecks nonblocking and no-replay
- `b75e2869295541b6f20e70bed590bfd2ee81ab80` — Add production recovery recheck concurrency regressions
- `43e769c49f3c6bc799c961d428cd9f1479cfbfba` — Add recovery recheck API regression
- `a1f4ef766136ff90ddf015493163b82981a3f80e` — Document no-replay recovery recheck flow
- `e9d9a80ffed75581fd8e49e133ecd006a1234f95` — Add operator recovery recheck safety regression
- `cb7a9d3a244d956ff7af0811879179ff260e7802` — Lock recovery recheck across durable restart

### Checks / results

- Authenticated GitHub connector reads/writes succeeded on `UnknownGod2011/Grafana` `main`.
- The intended delta from the previous head was reviewed with a commit comparison; changes are limited to `OPERATOR_CONSOLE.md`, the remediation/lifecycle/API/operator runtime modules, production execution-safe composition, and the new focused regression modules.
- A fresh checkout plus focused unittest execution was attempted with `git clone --depth 1 https://github.com/UnknownGod2011/Grafana.git` followed by the new recovery-recheck test modules.
- The runner again failed before checkout with `Could not resolve host: github.com`; therefore none of the newly committed recovery-recheck tests are claimed green in this run.
- Existing operator-console string assertions were inspected against the updated asset to avoid silently removing established fail-closed/no-replay expectations.
- The Cloud Logging audit validator was inspected: the new `recovery_rechecked` payload contains only bounded scalar fields (`revision`, `status`, `sample_count`, `provider_replayed`) and does not introduce blocked secret/query/endpoint keys.
- No GitHub Actions workflow was triggered merely to bypass the runner DNS failure.

### Decisions

1. `recovery_unverified` is not success and is not permission to replay the provider action; it is permission only to gather fresh recovery evidence.
2. Recovery-only verification is structurally separated from remediation dispatch by an API that does not receive a remediation client.
3. Recheck eligibility is derived entirely from durable server-side lifecycle state; the client cannot supply an action, target, datasource, query, operation ID, or force flag.
4. Successful rechecks preserve the original evidence revision and consumed approval because they are proving the result of the already-approved action, not authorizing a new action.
5. Production rechecks use the existing execution watchdog/mutation gate for responsiveness and concurrency safety, but expose `resolved` rather than `dispatching` while only telemetry is being polled.
6. A recovery-query failure cannot justify provider-execution uncertainty because the provider is not contacted; the prior unverified outcome remains authoritative and can be retried later.
7. The no-replay contract must remain valid across process restart, not only within one Python process.

### Blockers / unknowns

- The new recovery-only service/API/UI/concurrency/restart regressions still require a current executable checkout for actual execution.
- Recent audit/checkpoint/retention hardening regressions also still require a current executable checkout for consolidated execution.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- The real disposable private Cloud Run acceptance still requires a private StageGuard service, least-privilege ADC invoker identity, and Docker.
- Historical full-suite failures/errors remain untriaged; there is still no full-suite green claim.

## Single best next step

**Continue the end-to-end production workflow review at the incident lifecycle boundary after recovery: verify that `recovered` versus repeated `recovery_unverified` state is surfaced coherently in readiness/Prometheus metrics, durable checkpoint execution phase, timeline/audit reconstruction, and cold-restart operator UI; add any missing fixed-cardinality observability or restart/integration regressions without adding another provider-write path.**

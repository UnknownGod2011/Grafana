# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the read-only runtime evidence plane. The implemented vertical slice includes deterministic telemetry, Prometheus/Loki/Grafana, official Grafana MCP access, bounded diagnosis, optional Gemini briefing, exact-revision approval, remediation adapters, telemetry-verified recovery, authenticated lifecycle state, checkpoint/audit integrity, operator UI, Cloud Run deployment hardening, watchdog observability, authenticated private metrics bridging, strict evidence parsing, evidence-unavailable abstention, fail-closed HTTP/operator handling, explicit no-replay reconciliation for post-remediation persistence uncertainty, and versioned metric/Loki onboarding activation.

This file is intentionally compact; detailed earlier run history remains in Git history.

## Core invariants

- Grafana/MCP is read-only evidence access; infrastructure-write credentials remain isolated.
- Gemini is advisory and cannot mutate diagnosis, approval, remediation, or recovery state.
- Required evidence unavailability prevents briefing, approval, and execution from becoming actionable.
- Approval is exact-revision-bound and single-use.
- Provider action success never counts as recovery; fresh Grafana telemetry must prove recovery.
- Provider-controlled remediation detail/arbitrary metadata is discarded before lifecycle/API/audit state; only narrowly validated StageGuard production-operation metadata may survive.
- Durable checkpoint/audit failures fail closed; once provider dispatch may have occurred, persistence uncertainty blocks replay.
- Browser/API/onboarding/CLI surfaces must not expose provider failure detail or turn evidence loss into actionable state.
- Authentication failures expose only bounded StageGuard-owned messages.
- Expected evidence transport/protocol/datasource failures cross runtime boundaries as `EvidenceUnavailable`; unexpected programming/policy failures fail loudly internally and are redacted at process boundaries.
- Metric activation v2 pins the exact profile-derived ordered eight-query contract and normalized observed samples.
- Loki activation v2 pins the policy-owned LogQL/limit contract and bounded successful preflight evidence.
- Telemetry profiles require independent healthy comparators.
- Private Cloud Run metric requests reject redirects and keep token audience/target boundaries explicit.
- A metrics bridge bound beyond loopback requires explicit opt-in, inbound bearer authentication, strict token syntax, and a minimum 32-character credential.
- The reference Grafana MCP dependency is pinned to `grafana/mcp-grafana:1.4.1`; write/proxy restrictions and read-only tool annotations are regression-locked.
- Grafana MCP smoke requests, stdout frames, and pending-frame queues are bounded.
- Cloud Run remediation/recovery execution watchdog configuration is bounded to 1-600 seconds.
- Cloud Run checkpoint HMAC keys are bounded to 32-512 UTF-8 bytes and reject boundary whitespace/control characters.
- Evidence-plane readiness cache/backoff policy is finite and bounded: external probe TTL <= 300s, failure backoff <= 300s, stale-readiness grace <= 900s; booleans and NaN/infinity are rejected.

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected platform-specific permission test skipped on Windows.
- Focused core/API/UI suite from the last executable repository run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating the latest activation/checkpoint/readiness hardening.
- Historical official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`; pinned `1.4.1` still requires a live smoke before a production-ready claim.
- Recent hardening regressions have repeatedly been blocked from local execution because the automation runner cannot resolve `github.com`; do not infer green status from commits alone.

## Recently completed work

### Activation and onboarding

- Metric onboarding catches only `EvidenceUnavailable`, redacts provider detail, rejects non-finite samples, and fails unexpected programming/policy exceptions loudly.
- Metric activation v2 verifies the exact ordered profile-derived preflight contract, hashes normalized observed samples, and validates bounded persisted authority.
- Loki onboarding uses the same fail-closed/redacted error boundary.
- Loki activation v2 requires exact LogQL/limit, bounded line/window metadata, no truncation/error detail, canonical persisted-record shape, and bounded validity.

### Operator/process disclosure boundaries

- Preflight CLI failures return stable redacted failure envelopes.
- Unknown/custom identity-provider authentication detail collapses to `authentication required`.
- Remediation adapter result detail and arbitrary provider metadata are normalized away immediately after dispatch.
- Built-in production remediation retains only validated adapter identity, deterministic operation ID, bounded attempt count, and valid HTTP transport status.

### Cloud Run / MCP safety

- Cloud Run execution watchdog: 1-600 seconds in runtime and deploy helper.
- Checkpoint HMAC key: 32-512 UTF-8 bytes with whitespace/control rejection.
- Hermetic deploy-script regression prevents invalid watchdog values from reaching `gcloud`.
- Private metrics acceptance job identity is selector-safe and bounded before any Cloud Run/Docker action.
- Grafana MCP smoke has request deadlines, strict JSON-RPC/version/response-ID validation, 1 MiB frame cap, 16-frame pending queue cap, read-only surface enforcement, and image pin regressions.

## Run log — 2026-09-13 — readiness timing safety envelope

### Inspected at start

Read this `progress.md` completely before selecting work. Inspected repository contents and reviewed `runtime/readiness.py` plus `runtime/tests/test_readiness.py`. No unrelated repository, cloud resource, Grafana instance, Gemini endpoint, IAM binding, remediation provider, or GitHub Actions workflow was modified or manually triggered.

### Finding

`EvidencePlaneReadinessProbe` described its cache/backoff behavior as bounded, but constructor validation only checked positivity/order. Python boolean values were accepted as numeric seconds, `NaN` could bypass comparisons, infinity could create effectively permanent deadlines, and arbitrarily large TTL/backoff/stale-grace values could suppress fresh Grafana checks or keep stale evidence traffic-eligible for an operator-defined unbounded interval. This is especially significant because `stale` is deliberately considered readiness-eligible after a previously successful evidence-plane probe.

### Exact changes made

1. Added one centralized `_bounded_seconds()` validator in `runtime/readiness.py`.
2. Reject boolean and non-numeric timing inputs.
3. Reject NaN, positive/negative infinity, zero, and negative timing values.
4. Added explicit production safety ceilings:
   - external probe TTL: maximum 300 seconds;
   - failure retry backoff: maximum 300 seconds;
   - stale-readiness grace: maximum 900 seconds.
5. Preserved the existing invariant that stale grace must be at least the probe TTL.
6. Store only the normalized finite float values after validation.
7. Expanded `runtime/tests/test_readiness.py` with regressions for booleans, strings/None, NaN/infinity, values just above each safety ceiling, and exact maximum-boundary acceptance.

Commits:
- `112fbd931f3f89c503396a6410d9fc3d9c1b0f3f` — Harden readiness cache timing policy
- `f175a5dc018135259c25f5178f2870d13740b980` — Add readiness timing policy regressions

### Checks / results

- Authenticated GitHub connector reads and writes succeeded; both implementation and regression commits landed on `UnknownGod2011/Grafana` `main`.
- Attempted a real fresh checkout followed by `python -m unittest runtime.tests.test_readiness -v`.
- The execution runner failed before tests at `git clone --depth 1 https://github.com/UnknownGod2011/Grafana.git` with `Could not resolve host: github.com`.
- No GitHub Actions workflow was triggered merely to bypass this transient environment failure.
- Therefore the new readiness regressions are **not yet claimed green**.

### Decisions

1. Treat stale-readiness duration as a production safety policy rather than an unconstrained tuning knob because stale evidence remains traffic-eligible.
2. Keep ceilings generous relative to defaults (15s TTL, 5s backoff, 30s stale grace) while preventing permanent/effectively permanent stale state.
3. Reject booleans explicitly even though Python treats them as integers; configuration `true` must not silently become one second.
4. Preserve local/free operation and make no external paid-service dependency mandatory.

### Blockers / unknowns

- `runtime.tests.test_readiness` needs a current executable checkout.
- The prior remediation/auth/identity/activation/onboarding/Cloud Run focused suites still need a current executable checkout.
- MCP timeout/surface/image-pin regressions still need a current repository run.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- The real disposable private Cloud Run acceptance still requires a private StageGuard service, least-privilege ADC invoker identity, and Docker.
- Historical full-suite failures/errors remain untriaged; there is still no full-suite green claim.

## Single best next step

**As soon as executable checkout works, run `python -m unittest runtime.tests.test_readiness runtime.tests.test_remediation_result_boundary runtime.tests.test_remediation runtime.tests.test_production_remediation runtime.tests.test_incident_service runtime.tests.test_api_auth_error_redaction runtime.tests.test_identity runtime.tests.test_preflight_cli runtime.tests.test_activation runtime.tests.test_log_activation runtime.tests.test_onboarding runtime.tests.test_cloud_run_metrics_acceptance runtime.tests.test_telemetry runtime.tests.test_cloudrun_entrypoint runtime.tests.test_deploy_cloud_run_script -v`. Fix any regression before adding another production boundary. If clean, run the MCP timeout/surface/image-pin regressions and the live pinned Grafana MCP 1.4.1 smoke, then proceed to the private `ADC -> Cloud Run /metrics -> authenticated bridge -> Prometheus up: 1 -> 0 -> 1` acceptance.**

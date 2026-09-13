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
- Every `OperatorIdentity` enforces bounded string subject/provider fields and rejects ASCII control characters before identity data can cross API, audit, metrics, or logging boundaries.
- Non-development static bearer credentials must be 32-4096 UTF-8 bytes and use the RFC 6750 b64token character vocabulary; oversized request credentials are rejected before secret comparison.
- Expected evidence transport/protocol/datasource failures cross runtime boundaries as `EvidenceUnavailable`; unexpected programming/policy failures fail loudly internally and are redacted at process boundaries.
- Metric activation v2 pins the exact profile-derived ordered eight-query contract and normalized observed samples.
- Loki activation v2 pins the policy-owned LogQL/limit contract and bounded successful preflight evidence.
- Telemetry profiles require independent healthy comparators.
- Private Cloud Run metric requests reject redirects and keep token audience/target boundaries explicit.
- A metrics bridge bound beyond loopback requires explicit opt-in, inbound bearer authentication, strict token syntax, and a minimum 32-character credential.
- The reference Grafana MCP dependency is pinned to `grafana/mcp-grafana:1.4.1`; write/proxy restrictions and read-only tool annotations are regression-locked.
- Grafana MCP smoke requests, stdout frames, and pending-frame queues are bounded.
- The core remediation execution watchdog now enforces the same finite **1-600 second** policy as the Cloud Run boundary; alternate service embeddings cannot silently configure an effectively unbounded in-flight provider window.
- Cloud Run checkpoint HMAC keys are bounded to 32-512 UTF-8 bytes and reject boundary whitespace/control characters.
- Evidence-plane readiness cache/backoff policy is finite and bounded: external probe TTL <= 300s, failure backoff <= 300s, stale-readiness grace <= 900s; booleans and NaN/infinity are rejected.

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected platform-specific permission test skipped on Windows.
- Focused core/API/UI suite from the last executable repository run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating the latest activation/checkpoint/readiness/auth/watchdog hardening.
- Historical official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`; pinned `1.4.1` still requires a live smoke before a production-ready claim.
- Recent hardening regressions have repeatedly been blocked from local execution because the automation runner cannot resolve `github.com`; do not infer green status from commits alone.

## Recently completed work

### Activation and onboarding

- Metric onboarding catches only `EvidenceUnavailable`, redacts provider detail, rejects non-finite samples, and fails unexpected programming/policy exceptions loudly.
- Metric activation v2 verifies the exact ordered profile-derived preflight contract, hashes normalized observed samples, and validates bounded persisted authority.
- Loki onboarding uses the same fail-closed/redacted error boundary.
- Loki activation v2 requires exact LogQL/limit, bounded line/window metadata, no truncation/error detail, canonical persisted-record shape, and bounded validity.

### Operator/process disclosure and identity boundaries

- Preflight CLI failures return stable redacted failure envelopes.
- Unknown/custom identity-provider authentication detail collapses to `authentication required`.
- `OperatorIdentity` trims configured values, requires real strings, caps subject/provider sizes, and rejects ASCII controls.
- Static bearer identity refuses short, oversized, whitespace/control/malformed credentials at configuration time and bounds oversized untrusted bearer candidates before comparison.
- Remediation adapter result detail and arbitrary provider metadata are normalized away immediately after dispatch.
- Built-in production remediation retains only validated adapter identity, deterministic operation ID, bounded attempt count, and valid HTTP transport status.

### Cloud Run / MCP safety

- Core and Cloud Run remediation execution watchdog policy: 1-600 seconds.
- Checkpoint HMAC key: 32-512 UTF-8 bytes with whitespace/control rejection.
- Hermetic deploy-script regression prevents invalid watchdog values from reaching `gcloud`.
- Private metrics acceptance job identity is selector-safe and bounded before any Cloud Run/Docker action.
- Grafana MCP smoke has request deadlines, strict JSON-RPC/version/response-ID validation, 1 MiB frame cap, 16-frame pending queue cap, read-only surface enforcement, and image pin regressions.

## Run log — 2026-09-13 — core remediation watchdog policy

### Inspected at start

Read this `progress.md` completely before selecting work. Inspected the runtime tree, `runtime/anchored_execution_safety.py`, `runtime/tests/test_anchored_execution_safety.py`, and `runtime/cloudrun_entrypoint.py`. No unrelated repository, cloud resource, Grafana instance, Gemini endpoint, IAM binding, remediation provider, or GitHub Actions workflow was modified or manually triggered.

Also checked the official Grafana `mcp-grafana` latest release through GitHub. As of 2026-09-13, the latest published release is still **v1.4.1**, published 2026-09-11, so the repository's pin is current: https://github.com/grafana/mcp-grafana/releases/tag/v1.4.1

### Finding

`runtime/cloudrun_entrypoint.py` correctly restricted `STAGEGUARD_REMEDIATION_EXECUTION_MAX_SECONDS` to 1-600 seconds, but `AnchoredExecutionSafeIncidentService` itself accepted any finite positive number. Alternate production embeddings that instantiate the core service directly could therefore configure an hours- or days-long watchdog. During that interval an in-flight provider call remains `dispatching`, and the execution watchdog would not fail checkpoint/readiness state closed until the excessive deadline elapsed. The production safety invariant belonged in the core service, not only in one deployment adapter.

### Exact changes made

1. Added `MIN_REMEDIATION_EXECUTION_SECONDS = 1.0` and `MAX_REMEDIATION_EXECUTION_SECONDS = 600.0` to `runtime/anchored_execution_safety.py`.
2. Core service construction now rejects values below 1 second or above 600 seconds in addition to existing boolean, non-numeric, NaN, infinity, zero, and negative rejection.
3. Preserved the existing 60-second default.
4. Added focused `runtime/tests/test_execution_watchdog_bounds.py` covering exact lower/upper boundary acceptance and rejection of below-minimum, above-maximum, boolean, non-finite, and non-numeric values.

Commits:
- `cf564fe096cc83eedc24eac958aaaeac644d0606` — Bound remediation watchdog in core service
- `14ee91f538329d4298a04fbd76d20b7c424beb53` — Add core watchdog bound regressions

### Checks / results

- Authenticated GitHub connector reads/writes succeeded; both implementation and regression commits landed on `UnknownGod2011/Grafana` `main`.
- Re-read the committed implementation and regression file through the GitHub connector and verified the 1/600 constants and validation branches are present.
- Attempted a fresh executable checkout and focused run:
  `python -m unittest runtime.tests.test_execution_watchdog_bounds runtime.tests.test_anchored_execution_safety runtime.tests.test_cloudrun_entrypoint -v`
- The runner failed before checkout with `Could not resolve host: github.com`; therefore no repository tests executed locally and no new green claim is made.
- No GitHub Actions workflow was triggered merely to bypass the transient runner DNS failure.

### Decisions

1. Enforce the watchdog window inside the production service composition so CLI, test harnesses, alternate containers, and future deployment adapters cannot weaken the Cloud Run safety policy.
2. Keep the same 1-600 second range already used by Cloud Run rather than introducing a second policy window.
3. Keep the default at 60 seconds; this change only rejects unsafe/non-production configuration values.
4. Add a focused constructor-policy regression module rather than expanding a concurrency-heavy test fixture for simple boundary validation.

### Blockers / unknowns

- `runtime.tests.test_execution_watchdog_bounds` and the existing anchored-execution/Cloud Run tests need a current executable checkout.
- The identity/auth/readiness/remediation/activation/onboarding/Cloud Run focused suites still need a current executable checkout.
- MCP timeout/surface/image-pin regressions still need a current repository run.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- The real disposable private Cloud Run acceptance still requires a private StageGuard service, least-privilege ADC invoker identity, and Docker.
- Historical full-suite failures/errors remain untriaged; there is still no full-suite green claim.

## Single best next step

**As soon as executable checkout works, first run `python -m unittest runtime.tests.test_execution_watchdog_bounds runtime.tests.test_anchored_execution_safety runtime.tests.test_cloudrun_entrypoint -v`; fix any regression immediately. Then run the consolidated identity/auth/readiness/remediation/activation/onboarding/Cloud Run suite. If clean, run MCP timeout/surface/image-pin regressions and the live pinned Grafana MCP 1.4.1 smoke before the private `ADC -> Cloud Run /metrics -> authenticated bridge -> Prometheus up: 1 -> 0 -> 1` acceptance.**

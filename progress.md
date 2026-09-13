# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the read-only runtime evidence plane. The implemented vertical slice includes deterministic telemetry, Prometheus/Loki/Grafana, official Grafana MCP access, bounded investigation and diagnosis, optional Gemini briefing, exact-revision approval, remediation adapters, telemetry-verified recovery, authenticated lifecycle state, checkpoint/audit integrity, operator UI, Cloud Run deployment hardening, watchdog observability, authenticated private metrics bridging, evidence-unavailable abstention, fail-closed HTTP/operator handling, no-replay reconciliation for post-remediation persistence uncertainty, and versioned metric/Loki onboarding activation.

This file is intentionally compact; detailed earlier run history remains in Git history.

## Core invariants

- Grafana/MCP is read-only evidence access; infrastructure-write credentials remain isolated.
- Grafana MCP metric samples must be finite numeric evidence; JSON booleans are never accepted as `0`/`1` telemetry.
- Gemini is advisory and cannot mutate diagnosis, approval, remediation, or recovery state.
- Gemini context accepts only trusted identifiers, finite normalized numeric evidence, boolean/null hypothesis support, and confidence in [0, 1]; Vertex serialization forbids NaN/Infinity.
- Required evidence unavailability prevents briefing, approval, and execution from becoming actionable.
- Approval is exact-revision-bound and single-use.
- Provider action success never counts as recovery; fresh Grafana telemetry must prove recovery.
- Provider-controlled remediation detail/arbitrary metadata is discarded before lifecycle/API/audit state; only narrowly validated StageGuard production-operation metadata may survive.
- Durable checkpoint/audit failures fail closed; once provider dispatch may have occurred, persistence uncertainty blocks replay.
- Cloud Logging audit documents accept only finite numeric payload values, require true integer sequence/timestamps, and use strict JSON serialization with NaN/Infinity forbidden.
- Production remediation HTTP requests do not follow redirects; authorization/idempotency authority is non-redirectable and detectable final-URL changes fail closed.
- Browser/API/onboarding/CLI surfaces must not expose provider failure detail or turn evidence loss into actionable state.
- Authentication failures expose only bounded StageGuard-owned messages.
- Every `OperatorIdentity` enforces bounded string subject/provider fields and rejects ASCII control characters.
- Non-development static bearer credentials must be 32-4096 UTF-8 bytes and use the RFC 6750 b64token vocabulary; oversized request credentials are rejected before comparison.
- Expected evidence transport/protocol/datasource failures cross runtime boundaries as `EvidenceUnavailable`; unexpected programming/policy failures fail loudly internally and are redacted at process boundaries.
- Metric activation v2 pins the exact profile-derived ordered eight-query contract and normalized observed samples.
- Loki activation v2 pins the policy-owned LogQL/limit contract and bounded successful preflight evidence.
- Telemetry profiles require independent healthy comparators.
- Private Cloud Run metric requests reject redirects and keep token audience/target boundaries explicit.
- A metrics bridge bound beyond loopback requires explicit opt-in, inbound bearer authentication, strict token syntax, and a minimum 32-character credential.
- Private metrics bridge upstream waits are bounded to 60 seconds; configured inbound bearer secrets are capped at 4096 token characters and oversized presented credentials are rejected before comparison.
- The reference Grafana MCP dependency is pinned to `grafana/mcp-grafana:1.4.1`; write/proxy restrictions and read-only tool annotations are regression-locked.
- Grafana MCP smoke requests, stdout frames, and pending-frame queues are bounded.
- The core remediation execution watchdog enforces the same finite 1-600 second policy as the Cloud Run boundary.
- Cloud Run checkpoint HMAC keys are bounded to 32-512 UTF-8 bytes and reject boundary whitespace/control characters.
- Evidence-plane readiness cache/backoff policy is finite and bounded: external probe TTL <= 300s, failure backoff <= 300s, stale-readiness grace <= 900s; booleans and NaN/infinity are rejected.

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected platform-specific permission test skipped on Windows.
- Focused core/API/UI suite from the last executable repository run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating the latest activation/checkpoint/readiness/auth/watchdog/bridge/Gemini/remediation/MCP/audit hardening.
- Historical official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`; pinned `1.4.1` still requires a live smoke before a production-ready claim.
- Recent hardening regressions remain blocked from repository execution because the automation runner cannot resolve `github.com`; commits are not treated as passing tests.

## Recently completed work

### Activation / onboarding

- Metric and Loki onboarding redact provider detail, fail closed on expected evidence failures, reject malformed/non-finite evidence, and keep unexpected programming/policy failures loud.
- Metric activation v2 verifies the exact ordered profile-derived preflight contract and normalized samples.
- Loki activation v2 requires exact LogQL/limit, bounded line/window metadata, canonical persisted records, and bounded validity.

### Operator / identity / process boundaries

- Preflight CLI failures return stable redacted envelopes.
- Unknown/custom identity-provider detail collapses to `authentication required`.
- `OperatorIdentity` trims and bounds fields and rejects ASCII controls.
- Static bearer identity rejects short, oversized, whitespace/control/malformed credentials and bounds attacker-controlled candidates before comparison.
- Remediation provider detail and arbitrary metadata are normalized away before lifecycle/API/audit state.

### Gemini / remediation / runtime safety

- Gemini metric evidence rejects boolean/non-numeric/non-finite values; confidence is finite in [0, 1]; Vertex JSON serialization forbids NaN/Infinity.
- Core and Cloud Run remediation execution watchdog policy is 1-600 seconds.
- Checkpoint HMAC key policy is 32-512 UTF-8 bytes with whitespace/control rejection.
- Private metrics bridge timeout is capped at 60 seconds and bearer credentials at 4096 characters.
- Grafana MCP smoke has request deadlines, strict JSON-RPC/version/response-ID validation, 1 MiB frame cap, 16-frame pending queue cap, read-only surface enforcement, and image-pin regressions.
- Production remediation transport disables automatic redirects, marks `Authorization` and `Idempotency-Key` non-redirectable, and fails closed on detectable final-URL changes.
- Cloud Logging audit payloads reject NaN/Infinity, audit sequence/timestamps reject bool/float confusion, and audit JSON serialization is strict.

## Run log — 2026-09-13 — Cloud Logging audit numeric integrity

### Inspected at start

Read this `progress.md` completely before selecting work. Inspected repository metadata/runtime tree, `runtime/cloud_audit.py`, and `runtime/tests/test_cloud_audit.py`. No unrelated repository, cloud resource, Grafana instance, Gemini endpoint, IAM binding, remediation provider, or GitHub Actions workflow was modified or triggered.

### Finding

`cloud_audit._validate_scalar()` accepted every Python `float`, including `NaN`, `Infinity`, and `-Infinity`. Python's default `json.dumps()` allows those values and emits non-standard JSON tokens. The audit envelope also relied only on numeric comparisons for sequence/timestamp, so Python booleans could satisfy integer-shaped checks and floats such as `7.0` could pass some semantics even though lifecycle audit ordering/time fields are intended to be exact integers.

### Exact changes made

1. Added finite-number validation for every top-level and one-level nested audit payload scalar.
2. Tightened audit envelope validation so `sequence` and `timestamp_unix_ms` must be genuine non-boolean integers with the existing positive/non-negative constraints.
3. Switched the size-check serialization path to `json.dumps(..., allow_nan=False)` as a second fail-closed defense against future validation regressions.
4. Added focused regressions for NaN/±Infinity at both supported payload depths, boolean/float sequence and timestamp confusion, and valid finite numeric payloads.

Commits:
- `dcc821426454f4ad985cdac1ca268eaec51ea61a` — Harden Cloud Logging audit numeric integrity
- `98bef0070d7f3f0a5e8bd46f6f51fd101ebe5929` — Add Cloud audit numeric boundary regressions

### Checks / results

- Authenticated GitHub connector reads/writes succeeded and both implementation/test commits landed on `UnknownGod2011/Grafana` `main`.
- Attempted a fresh checkout followed by `PYTHONPATH=runtime python -m unittest runtime.tests.test_cloud_audit -v`.
- Checkout failed before tests with `Could not resolve host: github.com`.
- Therefore the committed Cloud audit regression suite did not execute from the repository in this run and no new green-suite claim is made.
- No GitHub Actions workflow was triggered merely to bypass the transient runner DNS failure.

### Decisions

1. Audit records are a durable authority boundary; malformed non-finite values must be rejected rather than normalized or logged.
2. Audit ordering and timestamps are integer contracts, not generic numeric contracts; Python bool/float coercion is rejected explicitly.
3. Keep strict serialization in addition to field validation so future payload-schema expansion cannot silently reintroduce NaN/Infinity.

### Blockers / unknowns

- The new `test_cloud_audit` regressions need a current executable checkout.
- Recent MCP, Gemini, metrics-bridge, watchdog, identity/auth/readiness/remediation/activation/onboarding/Cloud Run suites still need a current executable checkout.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- The real disposable private Cloud Run acceptance still requires a private StageGuard service, least-privilege ADC invoker identity, and Docker.
- Historical full-suite failures/errors remain untriaged; there is still no full-suite green claim.

## Single best next step

**As soon as executable checkout works, run `PYTHONPATH=runtime python -m unittest runtime.tests.test_cloud_audit runtime.tests.test_mcp_metric_client runtime.tests.test_mcp_log_client runtime.tests.test_mcp_smoke_timeout runtime.tests.test_mcp_smoke_surface -v` and fix any failure immediately. If clean, run the consolidated recent hardening suites, then the live pinned Grafana MCP 1.4.1 smoke before the private `ADC -> Cloud Run /metrics -> authenticated bridge -> Prometheus up: 1 -> 0 -> 1` acceptance.**

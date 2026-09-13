# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the read-only runtime evidence plane. The implemented vertical slice includes deterministic telemetry, Prometheus/Loki/Grafana, official Grafana MCP access, bounded investigation and diagnosis, optional Gemini briefing, exact-revision approval, remediation adapters, telemetry-verified recovery, authenticated lifecycle state, checkpoint/audit integrity, operator UI, Cloud Run deployment hardening, watchdog observability, authenticated private metrics bridging, evidence-unavailable abstention, fail-closed HTTP/operator handling, no-replay reconciliation for post-remediation persistence uncertainty, and versioned metric/Loki onboarding activation.

This file is intentionally compact; detailed earlier run history remains in Git history.

## Core invariants

- Grafana/MCP is read-only evidence access; infrastructure-write credentials remain isolated.
- Incident investigation accepts only `None` or finite non-boolean numeric metric samples from any adapter; malformed samples become bounded evidence-unavailable abstentions before threshold evaluation.
- Recovery verification independently accepts only `None` or finite non-boolean `int`/`float` metric samples from any adapter; malformed recovery samples become unavailable evidence and can never advance the healthy streak.
- A remediation adapter authorizes post-action verification only with literal boolean `accepted is True`; truthy strings, integers, containers, or other malformed acceptance flags fail closed as `action_failed`.
- Loki corroboration independently validates adapter envelopes, exact requested evidence windows, truncation type, record budget, record shape, string maps, scope, and event identity before evidence can corroborate a diagnosis.
- Grafana MCP metric samples must be finite numeric evidence; JSON booleans are never accepted as `0`/`1` telemetry.
- Gemini is advisory and cannot mutate diagnosis, approval, remediation, or recovery state.
- Gemini context accepts only trusted identifiers, finite normalized numeric evidence, boolean/null hypothesis support, and confidence in [0, 1]; Vertex serialization forbids NaN/Infinity.
- Required evidence unavailability prevents briefing, approval, and execution from becoming actionable.
- Approval is exact-revision-bound and single-use.
- Provider action success never counts as recovery; fresh Grafana telemetry must prove recovery.
- Provider-controlled remediation detail/arbitrary metadata is discarded before lifecycle/API/audit state; only narrowly validated StageGuard production-operation metadata may survive.
- Durable checkpoint/audit failures fail closed; once provider dispatch may have occurred, persistence uncertainty blocks replay.
- Cloud Logging audit documents accept only finite numeric payload values, true integer sequence/timestamps, bounded UTF-8 envelope strings without ASCII controls, and strict JSON serialization with NaN/Infinity forbidden.
- Audit hash-chain canonicalization uses strict JSON and refuses NaN/Infinity.
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
- The remediation watchdog validates its monotonic clock before durable dispatch, and any active-clock corruption, non-finite value, type drift, exception, or backward movement fails readiness closed as execution uncertainty.
- Cloud Run checkpoint HMAC keys are bounded to 32-512 UTF-8 bytes and reject boundary whitespace/control characters.
- Evidence-plane readiness cache/backoff policy is finite and bounded: external probe TTL <= 300s, failure backoff <= 300s, stale-readiness grace <= 900s; booleans and NaN/infinity are rejected.

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected platform-specific permission test skipped on Windows.
- Focused core/API/UI suite from the last executable repository run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating the latest activation/checkpoint/readiness/auth/watchdog/bridge/Gemini/remediation/MCP/audit/investigator/log/recovery hardening.
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

### Evidence / Gemini / remediation / runtime safety

- The core investigator independently normalizes metric evidence and refuses booleans, strings, NaN, and infinities from any metric adapter before incident threshold logic.
- Recovery verification independently normalizes post-action telemetry and refuses booleans, strings/objects, NaN, and infinities before any healthy-threshold comparison; valid finite integer samples are normalized to floats.
- Remediation result normalization now requires literal boolean `True` for provider acceptance; arbitrary truthy values cannot cause post-action verification to begin.
- Core Loki corroboration independently rejects malformed result envelopes, non-boolean truncation flags, query-window drift, non-tuple/over-budget record sets, and malformed record fields/maps before scope/event evaluation.
- Grafana MCP metric parsing independently rejects boolean and non-finite samples.
- Gemini metric evidence rejects boolean/non-numeric/non-finite values; confidence is finite in [0, 1]; Vertex JSON serialization forbids NaN/Infinity.
- Core and Cloud Run remediation execution watchdog policy is 1-600 seconds.
- Remediation watchdog clocks are now strict finite native numbers; invalid start clocks prevent durable dispatch/provider contact, and invalid/backward active clocks fail deadline/readiness closed.
- Checkpoint HMAC key policy is 32-512 UTF-8 bytes with whitespace/control rejection.
- Private metrics bridge timeout is capped at 60 seconds and bearer credentials at 4096 characters.
- Grafana MCP smoke has request deadlines, strict JSON-RPC/version/response-ID validation, 1 MiB frame cap, 16-frame pending queue cap, read-only surface enforcement, and image-pin regressions.
- Production remediation transport disables automatic redirects, marks `Authorization` and `Idempotency-Key` non-redirectable, and fails closed on detectable final-URL changes.
- Cloud Logging audit payloads reject NaN/Infinity, audit sequence/timestamps reject bool/float confusion, and audit JSON serialization is strict.
- Cloud Logging audit envelope strings are type-checked, UTF-8 byte-bounded, and reject ASCII controls.
- Audit hash-chain canonicalization rejects NaN/Infinity as non-canonical.

## Run log — 2026-09-13 — Recovery verification and remediation acceptance boundary

### Inspected at start

Read this `progress.md` completely before selecting work. Inspected the repository metadata/tree plus `runtime/incident_service.py`, `runtime/remediation.py`, `runtime/tests/test_remediation.py`, and `runtime/tests/test_remediation_result_boundary.py`. Attempted a fresh executable checkout before and after the changes. No unrelated repository, cloud resource, Grafana instance, Gemini endpoint, IAM binding, remediation provider, or GitHub Actions workflow was modified or triggered.

### Finding

The investigation and Grafana MCP paths already rejected boolean/non-finite telemetry, but `remediate_and_verify()` still consumed raw `MetricQueryClient.instant()` values during post-action recovery verification. Because Python booleans are integers, a custom/self-hosted adapter returning `False` for packet loss and dropped frames compared as numeric zero. With the default consecutive-health policy, repeated malformed boolean samples could therefore produce a false `recovered` transition after a real remediation action.

The same extension boundary also normalized `ActionResult.accepted` with `bool(...)`. That meant malformed provider output such as `1`, `"true"`, or another truthy object could be promoted to an accepted remediation result and begin recovery verification even though the adapter had violated its boolean contract.

### Exact changes made

1. Added `_normalize_recovery_metric()` in `runtime/remediation.py`.
2. Recovery samples now accept only explicit `None` or finite, non-boolean native `int`/`float` values; valid numbers are normalized to `float`.
3. Boolean, string, object, NaN, positive infinity, and negative infinity recovery values become unavailable (`None`) and cannot advance the healthy streak.
4. Preserved bounded polling and the existing rule that action acceptance is never itself proof of recovery.
5. Changed `sanitize_action_result()` so only literal `action.accepted is True` survives as acceptance; malformed truthy values fail closed as a locally redacted rejection.
6. Added regressions proving repeated `False` samples cannot false-positive recovery, `True` is not numeric evidence, NaN/infinities and strings/objects cannot prove recovery, one malformed sample resets a health streak, finite integer zero remains valid telemetry, and malformed truthy acceptance flags become `action_failed` before any metric query.

Commits:
- `3646ecb07c6a5edbfeb17fde75ec08e779a1443d` — Harden recovery telemetry evidence boundary
- `91282ec6cf9f7a588d8ba61160dabd06982a7015` — Add recovery metric boundary regressions
- `b89217037030304262d4105d37930d21cc0f4f5a` — Fail closed on malformed remediation acceptance flags
- `61f6413fff22a67a303dcbd890eaef791c6844fe` — Add malformed remediation acceptance regressions

### Checks / results

- Authenticated GitHub connector reads/writes succeeded and all implementation/test commits landed on `UnknownGod2011/Grafana` `main`.
- Attempted fresh checkout and focused execution: `PYTHONPATH=runtime python -m unittest runtime.tests.test_remediation runtime.tests.test_remediation_result_boundary -v`.
- DNS resolution produced no `github.com` address and checkout failed before tests with `Could not resolve host: github.com`.
- The new tests are therefore not claimed green, and no GitHub Actions workflow was triggered merely to bypass the transient runner DNS failure.

### Decisions

1. Recovery is a safety-critical state transition and must validate telemetry again at the recovery decision boundary even if the official Grafana MCP adapter already validates samples.
2. Malformed post-action evidence is treated as unavailable, not healthy; this keeps the incident open as `recovery_unverified` instead of crashing or granting recovery.
3. Provider acceptance is an authority bit, so permissive Python truthiness is inappropriate. Only literal boolean `True` can authorize the verification phase.
4. Native finite integers remain supported because legitimate metric adapters may return `0`/`1`; they are normalized to floats, while booleans are explicitly excluded.

### Blockers / unknowns

- `runtime.tests.test_remediation` and `runtime.tests.test_remediation_result_boundary` need a current executable checkout.
- Recent audit, MCP, Gemini, metrics-bridge, watchdog, identity/auth/readiness/remediation/activation/onboarding/Cloud Run/investigator/Loki hardening suites still need a current executable checkout.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- The real disposable private Cloud Run acceptance still requires a private StageGuard service, least-privilege ADC invoker identity, and Docker.
- Historical full-suite failures/errors remain untriaged; there is still no full-suite green claim.

## Run log — 2026-09-13 — Remediation watchdog clock integrity

### Inspected at start

Read this `progress.md` completely before selecting work. Inspected repository metadata/tree, `runtime/anchored_execution_safety.py`, and `runtime/tests/test_anchored_execution_safety.py`. No unrelated repository, cloud resource, Grafana instance, Gemini endpoint, IAM binding, remediation provider, or GitHub Actions workflow was modified or triggered.

### Finding

The remediation watchdog bounded configured execution duration but trusted every runtime value returned by the injectable monotonic clock. During an active execution, `NaN` caused the `age > maximum` deadline comparison to remain false, and a backward-moving clock was clamped to zero. A malformed custom clock could therefore make an in-flight remediation appear indefinitely within deadline. Invalid start-clock values were also read only after the durable dispatch barrier was persisted, creating avoidable ambiguous durable state even though provider contact had not yet begun.

### Exact changes made

1. Added `_read_execution_monotonic()` in `runtime/anchored_execution_safety.py`; watchdog readings must now be finite native `int`/`float` values and may not be booleans, strings, exceptions, NaN, or infinities.
2. The start clock is validated before `_persist_dispatching_barrier()`. A broken local clock now prevents provider contact without writing durable state that suggests dispatch may already have happened.
3. Active clock exceptions, type drift, non-finite values, arithmetic non-finiteness, or backward movement map to a bounded synthetic age of `execution_max_seconds + 1`, making `deadline_exceeded=True` and `checkpoint_state()` return `execution_uncertain`.
4. Added `runtime/tests/test_execution_watchdog_clock_boundary.py` covering invalid start clocks, zero provider calls on start-clock failure, active clock corruption, and backward movement.

Commits:
- `3814f3bed7d62115fbd3fc426b30af3b7ee90af4` — Fail closed on invalid remediation watchdog clocks
- `d4e8146bf453ca9d148429aaef951091e179c892` — Add remediation watchdog clock regressions

### Checks / results

- Authenticated GitHub connector reads/writes succeeded and both implementation/test commits landed on `UnknownGod2011/Grafana` `main`.
- Attempted fresh checkout and focused execution: `PYTHONPATH=runtime python -m unittest runtime.tests.test_execution_watchdog_clock_boundary runtime.tests.test_anchored_execution_safety -v`.
- Checkout failed before tests with `Could not resolve host: github.com`.
- The new tests are therefore not claimed green. No GitHub Actions workflow was triggered merely to bypass the transient runner DNS failure.

### Decisions

1. The watchdog is part of the no-replay/remediation safety boundary, so its own clock dependency must fail closed rather than silently disable deadline enforcement.
2. A broken clock before provider contact is a local precondition failure, not execution uncertainty; validating it before the durable dispatch barrier keeps that distinction exact.
3. Once execution is active, clock corruption is indistinguishable from an untrustworthy execution age, so readiness must become `execution_uncertain` immediately.
4. The fail-closed synthetic age remains finite and fixed-cardinality, preserving safe metrics/API serialization.

### Blockers / unknowns

- The new watchdog tests and existing anchored execution-safety suite require a current executable checkout.
- Recent remediation, audit, MCP, Gemini, metrics-bridge, identity/auth/readiness/activation/onboarding/Cloud Run/investigator/Loki hardening suites still need a current executable checkout.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- The real disposable private Cloud Run acceptance still requires a private StageGuard service, least-privilege ADC invoker identity, and Docker.
- Historical full-suite failures/errors remain untriaged; there is still no full-suite green claim.

## Single best next step

**As soon as executable checkout works, first run `PYTHONPATH=runtime python -m unittest runtime.tests.test_execution_watchdog_clock_boundary runtime.tests.test_anchored_execution_safety runtime.tests.test_remediation runtime.tests.test_remediation_result_boundary runtime.tests.test_log_evidence runtime.tests.test_mcp_log_client runtime.tests.test_investigator runtime.tests.test_mcp_metric_client -v` and fix any failure immediately. If clean, run the accumulated audit/Gemini/auth/readiness/bridge/activation suites, then the live pinned Grafana MCP 1.4.1 smoke before the private `ADC -> Cloud Run /metrics -> authenticated bridge -> Prometheus up: 1 -> 0 -> 1` acceptance.**

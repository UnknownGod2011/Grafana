# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the read-only runtime evidence plane. The implemented vertical slice includes deterministic telemetry, Prometheus/Loki/Grafana, official Grafana MCP access, bounded investigation and diagnosis, optional Gemini briefing, exact-revision approval, remediation adapters, telemetry-verified recovery, authenticated lifecycle state, checkpoint/audit integrity, operator UI, Cloud Run deployment hardening, watchdog observability, authenticated private metrics bridging, evidence-unavailable abstention, fail-closed HTTP/operator handling, no-replay reconciliation for post-remediation persistence uncertainty, and versioned metric/Loki onboarding activation.

This file is intentionally compact; detailed earlier run history remains in Git history.

## Core invariants

- Grafana/MCP is read-only evidence access; infrastructure-write credentials remain isolated.
- Incident investigation accepts only `None` or finite non-boolean numeric metric samples from any adapter; malformed samples become bounded evidence-unavailable abstentions before threshold evaluation.
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
- Cloud Run checkpoint HMAC keys are bounded to 32-512 UTF-8 bytes and reject boundary whitespace/control characters.
- Evidence-plane readiness cache/backoff policy is finite and bounded: external probe TTL <= 300s, failure backoff <= 300s, stale-readiness grace <= 900s; booleans and NaN/infinity are rejected.

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected platform-specific permission test skipped on Windows.
- Focused core/API/UI suite from the last executable repository run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating the latest activation/checkpoint/readiness/auth/watchdog/bridge/Gemini/remediation/MCP/audit/investigator hardening.
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

- The core investigator independently normalizes metric evidence and refuses booleans, strings, NaN, and infinities from any metric adapter before incident threshold logic; malformed samples produce semantic-slot evidence-unavailable abstention and stop further reads.
- Grafana MCP metric parsing independently rejects boolean and non-finite samples.
- Gemini metric evidence rejects boolean/non-numeric/non-finite values; confidence is finite in [0, 1]; Vertex JSON serialization forbids NaN/Infinity.
- Core and Cloud Run remediation execution watchdog policy is 1-600 seconds.
- Checkpoint HMAC key policy is 32-512 UTF-8 bytes with whitespace/control rejection.
- Private metrics bridge timeout is capped at 60 seconds and bearer credentials at 4096 characters.
- Grafana MCP smoke has request deadlines, strict JSON-RPC/version/response-ID validation, 1 MiB frame cap, 16-frame pending queue cap, read-only surface enforcement, and image-pin regressions.
- Production remediation transport disables automatic redirects, marks `Authorization` and `Idempotency-Key` non-redirectable, and fails closed on detectable final-URL changes.
- Cloud Logging audit payloads reject NaN/Infinity, audit sequence/timestamps reject bool/float confusion, and audit JSON serialization is strict.
- Cloud Logging audit envelope strings are type-checked, UTF-8 byte-bounded, and reject ASCII controls.
- Audit hash-chain canonicalization rejects NaN/Infinity as non-canonical.

## Run log — 2026-09-13 — investigator metric evidence boundary

### Inspected at start

Read this `progress.md` completely before selecting work. Inspected repository metadata/tree, `runtime/investigator.py`, `runtime/tests/test_investigator.py`, `runtime/telemetry.py`, `runtime/log_evidence.py`, and `runtime/evidence_errors.py`. Also attempted a fresh executable checkout before changing code. No unrelated repository, cloud resource, Grafana instance, Gemini endpoint, IAM binding, remediation provider, or GitHub Actions workflow was modified or triggered.

### Finding

The reference Grafana MCP metric adapter already rejects malformed samples, but the core investigator trusted every `MetricQueryClient` implementation to honor `float | None`. This was unsafe for a modular production system: Python booleans participate in numeric comparisons, positive infinity can satisfy incident thresholds, and `NaN` makes ordered comparisons false. In particular, a `NaN` symptom sample could fall through `if not value > 1.0` and incorrectly produce `no_incident`, while infinity in causal evidence could become diagnosis authority. Alternate/self-hosted adapters therefore had a path to influence lifecycle decisions with corrupt numeric evidence.

### Exact changes made

1. Added `_normalize_metric_value()` at the investigator boundary. It accepts `None` or finite `int`/`float`, rejects `bool`, non-numeric values, `NaN`, and infinities, and normalizes accepted numbers to `float`.
2. Invalid adapter samples are converted to `EvidenceUnavailable` inside the bounded collection loop, producing the existing sanitized abstention naming only the semantic slot and stopping additional evidence reads.
3. Unexpected adapter/programming exceptions remain loud; only evidence unavailability/corruption follows the operational abstention path.
4. Added regressions covering `True`, `False`, `NaN`, positive/negative infinity, numeric strings, arbitrary objects, invalid later-slot samples, early-stop query budgeting, and finite integer normalization.

Commits:
- `b14cd240632207b15e447ee409961193078feb23` — Harden investigator metric evidence boundary
- `5c6a4ef355ad337d5736f8aaa333514466c8e1b4` — Add investigator metric-boundary regressions

### Checks / results

- Authenticated GitHub connector reads/writes succeeded and both implementation/test commits landed on `UnknownGod2011/Grafana` `main`.
- Before modification, attempted `git clone --depth 1 https://github.com/UnknownGod2011/Grafana.git /tmp/stageguard`; checkout failed with `Could not resolve host: github.com`.
- Because the executable runner cannot currently resolve GitHub, `PYTHONPATH=runtime python -m unittest runtime.tests.test_investigator -v` could not be run from a fresh repository checkout in this run.
- The new tests are therefore not claimed green, and no GitHub Actions workflow was triggered merely to bypass the transient runner DNS failure.

### Decisions

1. Evidence validity must be enforced at the decision boundary as well as in the reference Grafana MCP adapter because StageGuard explicitly supports modular/custom telemetry integrations.
2. Corrupt/malformed metric samples are operationally equivalent to unavailable evidence and must cause abstention, never a healthy verdict or diagnosis.
3. Finite Python integers remain accepted and are normalized to floats because custom adapters may decode valid JSON/Prometheus numeric values as integers; booleans are excluded explicitly despite being `int` subclasses in Python.
4. The existing behavior for unexpected programming errors is preserved so defects are not silently hidden as evidence outages.

### Blockers / unknowns

- `runtime.tests.test_investigator` and the accumulated recent hardening regressions need a current executable checkout.
- Recent audit, MCP, Gemini, metrics-bridge, watchdog, identity/auth/readiness/remediation/activation/onboarding/Cloud Run suites still need a current executable checkout.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- The real disposable private Cloud Run acceptance still requires a private StageGuard service, least-privilege ADC invoker identity, and Docker.
- Historical full-suite failures/errors remain untriaged; there is still no full-suite green claim.

## Single best next step

**As soon as executable checkout works, run `PYTHONPATH=runtime python -m unittest runtime.tests.test_investigator runtime.tests.test_audit_integrity runtime.tests.test_cloud_audit runtime.tests.test_mcp_metric_client runtime.tests.test_mcp_log_client runtime.tests.test_mcp_smoke_timeout runtime.tests.test_mcp_smoke_surface -v` and fix any failure immediately. If clean, run the consolidated recent hardening suites, then the live pinned Grafana MCP 1.4.1 smoke before the private `ADC -> Cloud Run /metrics -> authenticated bridge -> Prometheus up: 1 -> 0 -> 1` acceptance.**

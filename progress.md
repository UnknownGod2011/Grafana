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
- Cloud Logging audit documents accept only finite numeric payload values, true integer sequence/timestamps, bounded UTF-8 envelope strings without ASCII controls, and strict JSON serialization with NaN/Infinity forbidden.
- Audit hash-chain canonicalization uses strict JSON and refuses NaN/Infinity, so values that cannot become valid durable numeric audit JSON cannot become authenticated chain authority.
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
- Cloud Logging audit envelope strings are now explicitly type-checked, UTF-8 byte-bounded, and reject ASCII controls so malformed custom events fail through a stable `ValueError` boundary instead of accidental attribute errors.
- Audit hash-chain canonicalization rejects NaN/Infinity as non-canonical rather than hashing Python-specific non-standard JSON tokens.

## Run log — 2026-09-13 — durable audit envelope boundary

### Inspected at start

Read this `progress.md` completely before selecting work. Inspected repository metadata, runtime tree, `runtime/cloud_audit.py`, `runtime/tests/test_cloud_audit.py`, `runtime/audit_integrity.py`, and the `AuditEvent`/local audit definitions in `runtime/incident_service.py`. No unrelated repository, cloud resource, Grafana instance, Gemini endpoint, IAM binding, remediation provider, or GitHub Actions workflow was modified or triggered.

### Finding

The Cloud Logging sink already bounded envelope lengths, but it called `.encode()` directly on `incident_id`, `event_type`, and `actor`. A malformed/custom `AuditEvent` with a non-string envelope field could therefore escape the sink's documented validation behavior as `AttributeError` instead of a stable `ValueError`. The same fields also accepted ASCII control characters, creating avoidable ambiguity in durable structured audit identifiers even though the authenticated operator identity boundary already rejects them.

### Exact changes made

1. Added a shared envelope-string validator requiring a non-empty string, rejecting ASCII controls (`0x00-0x1f` and `0x7f`), and enforcing the existing limits by UTF-8 bytes: incident ID 256, event type 128, actor 512.
2. Added explicit `AuditEvent` and payload-mapping validation so malformed direct/custom sink callers fail through a stable audit validation boundary.
3. Preserved the existing payload field/key/nesting restrictions, strict finite-number policy, 16 KiB entry cap, and `allow_nan=False` serialization.
4. Added regressions for non-string envelope fields, CR/LF/NUL/ESC-style controls, exact UTF-8 byte boundaries including multibyte characters, and non-mapping payloads.

Commits:
- `890a3c722588ca4b222a91f350cb9b7e30d9e0fd` — Harden Cloud audit envelope string validation
- `58fbd3b3af1716b2de69af840cfe7bbf86227e64` — Add Cloud audit envelope validation regressions

### Checks / results

- Authenticated GitHub connector reads/writes succeeded and both implementation/test commits landed on `UnknownGod2011/Grafana` `main`.
- Before modifying code, attempted a fresh checkout and the pending focused suite: `PYTHONPATH=runtime python -m unittest runtime.tests.test_audit_integrity runtime.tests.test_cloud_audit runtime.tests.test_mcp_metric_client runtime.tests.test_mcp_log_client runtime.tests.test_mcp_smoke_timeout runtime.tests.test_mcp_smoke_surface -v`.
- Checkout again failed before tests with `Could not resolve host: github.com`.
- Therefore neither the pending regressions nor the new audit-envelope regressions executed from the repository in this run; no new green-suite claim is made.
- No GitHub Actions workflow was triggered merely to bypass the transient runner DNS failure.

### Decisions

1. Durable audit sinks should reject malformed custom/direct callers deterministically rather than leaking incidental Python exceptions.
2. Envelope size policy is measured in UTF-8 bytes because transport/storage cost is byte-based; multibyte identifiers must not bypass configured limits.
3. ASCII controls are not valid StageGuard durable audit identifiers even inside structured logging fields; this aligns the sink with the existing operator identity boundary.

### Blockers / unknowns

- The new `test_cloud_audit` regressions and the recent `test_audit_integrity` regressions need a current executable checkout.
- Recent MCP, Gemini, metrics-bridge, watchdog, identity/auth/readiness/remediation/activation/onboarding/Cloud Run suites still need a current executable checkout.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- The real disposable private Cloud Run acceptance still requires a private StageGuard service, least-privilege ADC invoker identity, and Docker.
- Historical full-suite failures/errors remain untriaged; there is still no full-suite green claim.

## Single best next step

**As soon as executable checkout works, run `PYTHONPATH=runtime python -m unittest runtime.tests.test_audit_integrity runtime.tests.test_cloud_audit runtime.tests.test_mcp_metric_client runtime.tests.test_mcp_log_client runtime.tests.test_mcp_smoke_timeout runtime.tests.test_mcp_smoke_surface -v` and fix any failure immediately. If clean, run the consolidated recent hardening suites, then the live pinned Grafana MCP 1.4.1 smoke before the private `ADC -> Cloud Run /metrics -> authenticated bridge -> Prometheus up: 1 -> 0 -> 1` acceptance.**

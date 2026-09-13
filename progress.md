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
- Every `OperatorIdentity` now enforces bounded string subject/provider fields and rejects ASCII control characters before identity data can cross API, audit, metrics, or logging boundaries.
- Non-development static bearer credentials must be 32-4096 UTF-8 bytes and use the RFC 6750 b64token character vocabulary; oversized request credentials are rejected before secret comparison.
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
- Historical live Docker rehearsal: PASS twice consecutively, predating the latest activation/checkpoint/readiness/auth hardening.
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
- `OperatorIdentity` trims configured values, requires real strings, caps subject/provider sizes, and rejects CR/LF/NUL/TAB/ESC/DEL and other ASCII controls.
- Static bearer identity refuses short, oversized, whitespace/control/malformed credentials at configuration time and bounds oversized untrusted bearer candidates before comparison.
- Remediation adapter result detail and arbitrary provider metadata are normalized away immediately after dispatch.
- Built-in production remediation retains only validated adapter identity, deterministic operation ID, bounded attempt count, and valid HTTP transport status.

### Cloud Run / MCP safety

- Cloud Run execution watchdog: 1-600 seconds in runtime and deploy helper.
- Checkpoint HMAC key: 32-512 UTF-8 bytes with whitespace/control rejection.
- Hermetic deploy-script regression prevents invalid watchdog values from reaching `gcloud`.
- Private metrics acceptance job identity is selector-safe and bounded before any Cloud Run/Docker action.
- Grafana MCP smoke has request deadlines, strict JSON-RPC/version/response-ID validation, 1 MiB frame cap, 16-frame pending queue cap, read-only surface enforcement, and image pin regressions.

## Run log — 2026-09-13 — operator identity field integrity

### Inspected at start

Read this `progress.md` completely before selecting work. Inspected the runtime tree, `runtime/bootstrap.py`, `runtime/identity.py`, and `runtime/tests/test_identity.py`. Also attempted a fresh executable checkout before implementation. No unrelated repository, cloud resource, Grafana instance, Gemini endpoint, IAM binding, remediation provider, or GitHub Actions workflow was modified or manually triggered.

### Finding

The static bearer token itself had already been hardened, but the common `OperatorIdentity` object only trimmed and byte-bounded the subject. It still allowed embedded ASCII control characters such as CR/LF, NUL, TAB, or ESC in authenticated subject strings, and its provider field had no size bound. Since identity data is reused for operator attribution across API, audit, metrics, and logging surfaces, a custom provider or malformed verified claim could create ambiguous/log-injection-shaped attribution even though authentication itself succeeded.

### Exact changes made

1. Added `MAX_IDENTITY_PROVIDER_BYTES = 128` alongside the existing 512-byte subject cap.
2. Added common identity-field validation rejecting ASCII control characters (`0x00-0x1f` and `0x7f`) after normalization.
3. Required both `OperatorIdentity.subject` and `.provider` to actually be strings instead of relying on `.strip()` failure behavior.
4. Preserved benign outer-whitespace normalization while rejecting embedded control characters.
5. Because all built-in providers construct `OperatorIdentity`, the boundary now protects local, static bearer, Google IAP, and custom-provider identities uniformly.
6. Expanded `runtime/tests/test_identity.py` with regressions for blank/non-string fields, oversize subject/provider values, CR/LF/NUL/ESC controls, exact limit acceptance, and a Google IAP `sub` containing a newline.

Commits:
- `cb5202449beb5f732d4215d5d998b6ce01b9b7ba` — Harden operator identity field boundaries
- `ecc0402b2e3443258a51982c11257ed67dae83e8` — Add operator identity field boundary regressions

### Checks / results

- Authenticated GitHub connector reads and writes succeeded; both commits landed on `UnknownGod2011/Grafana` `main`.
- Re-read the committed `runtime/identity.py` through the GitHub connector and verified the new provider cap, type checks, control-character validator, and normalized storage are present.
- Attempted `git clone --depth 1 https://github.com/UnknownGod2011/Grafana.git /tmp/stageguard-grafana`; the execution runner again failed with `Could not resolve host: github.com` before tests could run.
- No GitHub Actions workflow was triggered merely to bypass the transient environment failure.
- Therefore the updated `runtime.tests.test_identity` and broader focused suite are **not yet claimed green**.

### Decisions

1. Put the invariant on `OperatorIdentity`, not separately on each provider, so future identity adapters cannot accidentally bypass it.
2. Reject ASCII controls rather than over-restricting valid identity syntax; IAP subjects and organization-defined static subjects can retain ordinary Unicode/punctuation while remaining safe for structured attribution.
3. Bound provider identifiers independently because custom provider implementations are process extensions and should not be able to inject unbounded attribution metadata.
4. Keep outer-whitespace normalization for backward compatibility with process-configured subjects.

### Blockers / unknowns

- `runtime.tests.test_identity` needs a current executable checkout.
- The identity/auth/readiness/remediation/activation/onboarding/Cloud Run focused suites still need a current executable checkout.
- MCP timeout/surface/image-pin regressions still need a current repository run.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- The real disposable private Cloud Run acceptance still requires a private StageGuard service, least-privilege ADC invoker identity, and Docker.
- Historical full-suite failures/errors remain untriaged; there is still no full-suite green claim.

## Single best next step

**As soon as executable checkout works, run `python -m unittest runtime.tests.test_identity runtime.tests.test_api_auth_error_redaction runtime.tests.test_readiness runtime.tests.test_remediation_result_boundary runtime.tests.test_remediation runtime.tests.test_production_remediation runtime.tests.test_incident_service runtime.tests.test_preflight_cli runtime.tests.test_activation runtime.tests.test_log_activation runtime.tests.test_onboarding runtime.tests.test_cloud_run_metrics_acceptance runtime.tests.test_telemetry runtime.tests.test_cloudrun_entrypoint runtime.tests.test_deploy_cloud_run_script -v`. Fix any regression before adding another production boundary. If clean, run the MCP timeout/surface/image-pin regressions and the live pinned Grafana MCP 1.4.1 smoke, then proceed to the private `ADC -> Cloud Run /metrics -> authenticated bridge -> Prometheus up: 1 -> 0 -> 1` acceptance.**

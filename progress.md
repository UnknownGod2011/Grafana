# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the read-only runtime evidence plane. The implemented vertical slice includes deterministic telemetry, Prometheus/Loki/Grafana, official Grafana MCP access, bounded diagnosis, optional Gemini briefing, exact-revision approval, remediation adapters, telemetry-verified recovery, authenticated lifecycle state, checkpoint/audit integrity, operator UI, Cloud Run deployment hardening, watchdog observability, authenticated private metrics bridging, strict evidence parsing, evidence-unavailable abstention, fail-closed HTTP/operator handling, explicit no-replay reconciliation for post-remediation persistence uncertainty, and versioned metric/Loki onboarding activation.

This file is intentionally compact; detailed earlier run history remains in Git history.

## Core invariants

- Grafana/MCP is read-only evidence access; infrastructure-write credentials remain isolated.
- Gemini is advisory and cannot mutate diagnosis, approval, remediation, or recovery state.
- Gemini context accepts only trusted identifiers, finite normalized numeric evidence, boolean/null hypothesis support, and confidence in [0, 1]; Vertex serialization forbids NaN/Infinity.
- Required evidence unavailability prevents briefing, approval, and execution from becoming actionable.
- Approval is exact-revision-bound and single-use.
- Provider action success never counts as recovery; fresh Grafana telemetry must prove recovery.
- Provider-controlled remediation detail/arbitrary metadata is discarded before lifecycle/API/audit state; only narrowly validated StageGuard production-operation metadata may survive.
- Durable checkpoint/audit failures fail closed; once provider dispatch may have occurred, persistence uncertainty blocks replay.
- Production remediation HTTP requests do not follow redirects. Authorization and idempotency authority are marked non-redirectable, and detectable final-URL changes from trusted custom openers fail closed.
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
- Historical live Docker rehearsal: PASS twice consecutively, predating the latest activation/checkpoint/readiness/auth/watchdog/bridge/Gemini/remediation-transport hardening.
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

### Gemini advisory boundary

- `build_commander_context()` rejects boolean/non-numeric/non-finite metric values while preserving unavailable evidence as JSON null.
- Confidence is independently constrained to a finite value in [0, 1], and `supports_hypothesis` is boolean/null only.
- The Vertex AI adapter uses `json.dumps(..., allow_nan=False)` as defense in depth.

### Cloud Run / MCP / remediation safety

- Core and Cloud Run remediation execution watchdog policy: 1-600 seconds.
- Checkpoint HMAC key: 32-512 UTF-8 bytes with whitespace/control rejection.
- Private metrics bridge upstream timeout is capped at 60 seconds; inbound bearer tokens are capped at 4096 characters and oversized presented candidates are rejected before comparison.
- Grafana MCP smoke has request deadlines, strict JSON-RPC/version/response-ID validation, 1 MiB frame cap, 16-frame pending queue cap, read-only surface enforcement, and image pin regressions.
- Production remediation transport now disables automatic redirects, marks `Authorization` and `Idempotency-Key` as unredirected headers, and fails closed if a custom opener reports a changed final URL.

## Run log — 2026-09-13 — production remediation redirect authority

### Inspected at start

Read this `progress.md` completely before selecting work. Inspected repository metadata/tree, `runtime/http_remediation_transport.py`, `runtime/production_remediation.py`, `runtime/tests/test_http_remediation_transport.py`, and `runtime/tests/test_http_remediation_tls_integration.py`. Confirmed the production adapter performs write-capable remediation with a bearer credential and stable operation identity, while the HTTP transport previously delegated default networking to `urllib.request.urlopen`. No unrelated repository, cloud resource, Grafana instance, Gemini endpoint, IAM binding, remediation provider, or GitHub Actions workflow was modified or manually triggered.

### Finding

The credentialed production remediation transport used Python's default URL opener. Default HTTP redirect handling is unsuitable for a write-authority boundary: a redirect can transfer request handling away from the configured provider endpoint, and generic redirect semantics are not StageGuard remediation policy. The transport also placed `Authorization` and `Idempotency-Key` in normal request headers rather than explicitly making them non-redirectable. Even though the endpoint itself was HTTPS-validated, redirect authority was not independently constrained.

### Exact changes made

1. Added a dedicated `_RejectRedirects` handler and `_default_urlopen_no_redirect()` production opener; automatic HTTP redirects now raise `HTTPError` instead of being followed.
2. Added `_add_sensitive_header()` and moved remediation `Authorization` plus `Idempotency-Key` into `Request.add_unredirected_header(...)`; reconciliation bearer auth uses the same treatment.
3. Added `_response_matches_request()` as defense in depth for injected/custom openers: when a response exposes `geturl()`, execute rejects a changed final URL and reconciliation returns `unknown`.
4. Preserved the existing custom opener seam for deterministic TLS/integration testing and deployment-specific networking policy; its trust responsibility is now explicit in the transport docstring.
5. Added redirect regressions proving standard redirect construction does not copy the bearer credential/idempotency key, the production redirect handler refuses redirects, redirected custom-opener execution cannot become accepted, and redirected reconciliation cannot become authoritative.
6. Retained the existing strict response shape, 16 KiB response cap, operation echo, bounded retry-status policy, and GET-only reconciliation behavior.

Commits:
- `1d578dfca71298c4f018eab3fa8fc00ad06de5e4` — Harden remediation transport redirect safety
- `d03c0d19e69b26d1f3afe798ac7420b0a405f450` — Add remediation redirect-safety regressions

### Checks / results

- Authenticated GitHub connector reads/writes succeeded and both implementation/test commits landed on `UnknownGod2011/Grafana` `main`.
- Re-read both committed files through the GitHub connector and confirmed the no-redirect opener, non-redirectable authority headers, final-URL defense, and regressions are present.
- Independently exercised Python's redirect construction locally: an original request with `Authorization` and `Idempotency-Key` added through `add_unredirected_header()` produced a redirected request with neither header and no POST body; the reject-redirect handler raised `HTTPError` with the redirect status as intended.
- Attempted a fresh checkout followed by `PYTHONPATH=runtime python -m unittest runtime.tests.test_http_remediation_transport runtime.tests.test_http_remediation_tls_integration runtime.tests.test_execution_safety_http_transport runtime.tests.test_production_remediation -v`; checkout failed before tests with `Could not resolve host: github.com`.
- Therefore the committed remediation regression suite did not execute from the repository in this run and no new green-suite claim is made.
- No GitHub Actions workflow was triggered merely to bypass the transient runner DNS failure.

### Decisions

1. Redirects are not a valid remediation-provider authority transfer. A configured write endpoint must answer directly or execution fails closed.
2. Bearer credentials and idempotency authority are marked non-redirectable even though production redirects are already disabled, providing defense in depth and safer behavior for standard redirect machinery.
3. The custom opener remains available because the real loopback TLS tests and some deployments need a controlled networking seam; custom networking is trusted, while detectable final-URL changes are still rejected.
4. Redirect failures are not treated as transient retry authority merely because their HTTP status is 3xx; they remain non-retryable/unknown at the transport boundary.

### Blockers / unknowns

- The new remediation redirect regressions and adjacent HTTP/TLS/production-remediation suites need a current executable checkout.
- The Gemini commander, metrics-bridge bounds, core watchdog, identity/auth/readiness/remediation/activation/onboarding/Cloud Run focused suites still need a current executable checkout.
- MCP timeout/surface/image-pin regressions still need a current repository run.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- The real disposable private Cloud Run acceptance still requires a private StageGuard service, least-privilege ADC invoker identity, and Docker.
- Historical full-suite failures/errors remain untriaged; there is still no full-suite green claim.

## Single best next step

**As soon as executable checkout works, run `PYTHONPATH=runtime python -m unittest runtime.tests.test_http_remediation_transport runtime.tests.test_http_remediation_tls_integration runtime.tests.test_execution_safety_http_transport runtime.tests.test_production_remediation runtime.tests.test_gemini_commander runtime.tests.test_gemini_acceptance_smoke runtime.tests.test_cloud_run_metrics_bridge_bounds runtime.tests.test_cloud_run_metrics_bridge runtime.tests.test_execution_watchdog_bounds runtime.tests.test_cloudrun_entrypoint -v` and fix any failure immediately. If clean, run the consolidated identity/auth/readiness/remediation/activation/onboarding/Cloud Run suite, then MCP timeout/surface/image-pin regressions and the live pinned Grafana MCP 1.4.1 smoke before the private `ADC -> Cloud Run /metrics -> authenticated bridge -> Prometheus up: 1 -> 0 -> 1` acceptance.**

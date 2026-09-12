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
- Durable checkpoint/audit failures fail closed and uncommitted state is not operator-visible lifecycle authority.
- Once provider dispatch may have occurred, persistence uncertainty blocks replay.
- Browser/API/onboarding/CLI surfaces must not expose provider failure detail or turn evidence loss into actionable state.
- Authentication failures expose only the bounded StageGuard-owned message vocabulary; unknown/custom identity-provider detail collapses to `authentication required`.
- Expected evidence transport/protocol/datasource failures cross runtime boundaries as `EvidenceUnavailable`; unexpected programming/policy exceptions fail loudly inside the runtime and process-level entrypoints fail closed without exposing raw exception text.
- Metric and Loki activation records are bounded, schema/version validated, expiry constrained, datasource/contract pinned, and rejected when malformed.
- Telemetry activation v2 pins the exact profile-derived ordered eight-query contract and normalized observed samples.
- Loki activation v2 requires the exact policy-owned LogQL/limit contract and a bounded successful preflight with no error detail.
- Private Cloud Run metric requests reject redirects and keep token audience/target boundaries explicit.
- Runtime metric readiness requires an unambiguous StageGuard safety sentinel, not merely HTTP 200.
- A metrics bridge bound beyond loopback requires explicit network-bind opt-in, inbound bearer authentication, strict bearer-token syntax, and a minimum 32-character credential.
- The private Cloud Run acceptance harness uses one bounded selector-safe Prometheus job identity consistently in YAML and PromQL.
- The reference Grafana MCP dependency is pinned to `grafana/mcp-grafana:1.4.1`; server-side write/proxy restrictions and live `readOnlyHint=true` validation are regression-locked.
- Grafana MCP smoke requests are time-bounded; stdout JSON-RPC frames and pending-frame queue growth are bounded and framing/response integrity fails closed.
- Cloud Run remediation/recovery execution watchdog configuration is bounded to 1-600 seconds.
- Cloud Run checkpoint HMAC keys are bounded to 32-512 UTF-8 bytes and reject boundary whitespace/control characters.
- Telemetry profiles require independent healthy comparators.

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected platform-specific permission test skipped on Windows.
- Focused core/API/UI suite from the last executable repository run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating the latest activation/checkpoint/acceptance hardening.
- Historical official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`; pinned `1.4.1` still requires a live smoke before a production-ready claim.
- Recent MCP hardening added request deadlines, strict JSON-RPC framing/response-ID validation, a 1,048,576-character frame cap, and a 16-frame pending stdout queue; current repository regressions still need a runnable checkout.

## Recently completed work

### Metric onboarding / activation

- Enforced independent healthy comparator mappings.
- Onboarding catches only `EvidenceUnavailable`, redacts provider detail, rejects non-finite samples, and fails unexpected programming/policy exceptions loudly.
- Metric activation v2 verifies the exact ordered profile-derived preflight contract and hashes normalized observed sample values.
- Persisted/manual activation authority validates canonical SHA-256 digests, trimmed production identity, integer non-negative timestamps, strict expiry ordering, a seven-day maximum lifetime, and strict explicit-clock types.

### Loki onboarding / activation

- `preflight_loki()` catches only `EvidenceUnavailable` and emits stable redacted detail; unexpected programming/policy exceptions propagate.
- Loki activation v2 requires the exact policy-owned LogQL/limit contract, bounded line count/window metadata, no truncation/error detail, canonical persisted-record shape, and bounded validity.

### Operator/process disclosure boundaries

- Preflight CLI failures no longer serialize raw exception messages; they return a stable `ready=false` envelope plus exception class only.
- Authentication failures now preserve only a fixed StageGuard-owned public message set. Arbitrary `AuthenticationError` text from custom identity providers is converted to `authentication required` before existing API/console rendering can expose it.
- HTTP regression coverage exercises this behavior on `/console`, authenticated GET, and authenticated POST surfaces while retaining actionable built-in bearer/IAP messages.

### Cloud Run / MCP safety retained

- Cloud Run execution watchdog: 1-600 seconds in runtime and deployment helper.
- Checkpoint HMAC key: 32-512 UTF-8 bytes with whitespace/control rejection.
- Hermetic deploy-script regression prevents invalid watchdog values from reaching `gcloud`.
- Private metrics acceptance job identity is allowlisted and bounded before any Cloud Run/Docker action.
- Grafana MCP smoke has request deadlines, strict JSON-RPC/version/response-ID validation, 1 MiB frame cap, 16-frame pending queue cap, read-only surface enforcement, and image pin regressions.

## Run log — 2026-09-13 — authentication disclosure boundary

### Inspected at start

Read this `progress.md` completely before selecting work. Inspected repository metadata and reviewed:
- `README.md`
- `runtime/api.py`, including console, authenticated GET/POST, readiness, metrics, lifecycle, and error paths
- `runtime/identity.py`
- `runtime/incident_service.py` error/state semantics
- `runtime/tests/test_api.py`
- `runtime/tests/test_api_evidence_unavailable_mutations.py`
- `runtime/tests/test_identity.py`

No unrelated repository, cloud resource, Grafana instance, Gemini endpoint, IAM binding, remediation provider, or GitHub Actions job was modified or manually triggered.

### Finding

The API intentionally uses `str(AuthenticationError)` for 401 details on the operator console and authenticated GET/POST surfaces. Built-in StageGuard identity providers currently raise bounded messages, but `IdentityProvider` is an extension point. A custom provider could raise `AuthenticationError` containing verifier responses, private endpoints, tenant detail, or secret-bearing diagnostics, and the API would echo that text verbatim. This contradicted the existing operator-surface redaction invariant.

### Exact changes made

1. Hardened `runtime/identity.py` `AuthenticationError` with a fixed StageGuard-owned public-detail vocabulary.
2. Existing safe/actionable built-in messages remain unchanged (`invalid bearer credential`, `invalid IAP assertion`, etc.).
3. Any unknown/custom `AuthenticationError` string now renders as exactly `authentication required`; the original exception object/cause can still exist internally without its text crossing the HTTP boundary.
4. Added `runtime/tests/test_api_auth_error_redaction.py`.
5. The new HTTP-level regressions use a deliberately secret-bearing custom identity provider and verify redaction on:
   - `GET /console`
   - `GET /v1/incident`
   - `POST /v1/investigate`
6. The regression also verifies the expected `WWW-Authenticate` challenge remains and that StageGuard-owned bearer/IAP messages remain actionable.

Commits:
- `ec3f5a80c37d1ba2bfeab7b4dcc192dcc2356f60` — Harden authentication error disclosure boundary
- `365a0ec9cd7ea3b1d741030a8317a20e156dcc39` — Add authentication error redaction regressions

### Checks / results

- Authenticated GitHub repository reads/writes succeeded and both implementation/test commits landed on `UnknownGod2011/Grafana` `main`.
- Attempted the previously blocked focused suite from a fresh checkout before making changes:
  `python -m unittest runtime.tests.test_preflight_cli runtime.tests.test_activation runtime.tests.test_log_activation runtime.tests.test_onboarding runtime.tests.test_cloud_run_metrics_acceptance runtime.tests.test_telemetry runtime.tests.test_cloudrun_entrypoint runtime.tests.test_deploy_cloud_run_script -v`
- The execution environment again failed at `git clone --depth 1 https://github.com/UnknownGod2011/Grafana.git` with `Could not resolve host: github.com`; no repository tests executed in that runner.
- Checked GitHub for automatically associated workflow runs on the regression commit; none were present. No Actions workflow was manually rerun or triggered.
- Therefore the new `test_api_auth_error_redaction` module and the previously pending focused suite are **not yet claimed green**.

### Decisions

1. Keep actionable authentication messages for StageGuard-owned providers rather than making every 401 opaque.
2. Treat arbitrary/custom provider messages as untrusted disclosure input and collapse them to one stable generic detail.
3. Enforce this at the exception boundary so all current API/console `str(AuthenticationError)` call sites inherit the same rule without duplicated redaction logic.
4. Do not create CI noise solely to compensate for the transient runner DNS failure.

### Blockers / unknowns

- `runtime.tests.test_api_auth_error_redaction`, `runtime.tests.test_identity`, and the prior focused activation/onboarding/Cloud Run suite need a current executable checkout.
- MCP timeout/surface/image-pin regressions still need an actual repository run.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- The strengthened Cloud Run bridge and execution-reconciliation/operator/Playwright safety sets still need current execution.
- The real disposable private Cloud Run acceptance still requires a private StageGuard service, least-privilege ADC invoker identity, and Docker.
- Historical full-suite failures/errors remain untriaged; there is still no full-suite green claim.

## Single best next step

**As soon as executable checkout works, run `python -m unittest runtime.tests.test_api_auth_error_redaction runtime.tests.test_identity runtime.tests.test_preflight_cli runtime.tests.test_activation runtime.tests.test_log_activation runtime.tests.test_onboarding runtime.tests.test_cloud_run_metrics_acceptance runtime.tests.test_telemetry runtime.tests.test_cloudrun_entrypoint runtime.tests.test_deploy_cloud_run_script -v`. Fix any regression before adding another production boundary. If clean, run the MCP timeout/surface/image-pin regressions and the live pinned Grafana MCP 1.4.1 smoke, then proceed to the private `ADC -> Cloud Run /metrics -> authenticated bridge -> Prometheus up: 1 -> 0 -> 1` acceptance.**

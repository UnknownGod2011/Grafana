# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the read-only runtime evidence plane. The implemented vertical slice includes deterministic telemetry, Prometheus/Loki/Grafana, official Grafana MCP access, bounded diagnosis, optional Gemini briefing, exact-revision approval, remediation adapters, telemetry-verified recovery, authenticated lifecycle state, checkpoint/audit integrity, operator UI, Cloud Run deployment hardening, watchdog observability, authenticated private metrics bridging, strict evidence parsing, evidence-unavailable abstention, fail-closed HTTP/operator handling, explicit no-replay reconciliation for post-remediation persistence uncertainty, and versioned metric/Loki onboarding activation.

This file is intentionally compact; detailed earlier run history remains in Git history.

## Core invariants

- Grafana/MCP is read-only evidence access; infrastructure-write credentials remain isolated.
- Gemini is advisory and cannot mutate diagnosis, approval, remediation, or recovery state.
- Gemini context accepts only trusted identifiers, finite normalized numeric evidence, boolean/null hypothesis support, and confidence in the closed probability range [0, 1]; the Vertex adapter serializes context as strict JSON with NaN/Infinity forbidden.
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
- Private metrics bridge upstream waits are bounded to 60 seconds; configured inbound bearer secrets are capped at 4096 token characters and oversized presented credentials are rejected before comparison.
- The reference Grafana MCP dependency is pinned to `grafana/mcp-grafana:1.4.1`; write/proxy restrictions and read-only tool annotations are regression-locked.
- Grafana MCP smoke requests, stdout frames, and pending-frame queues are bounded.
- The core remediation execution watchdog enforces the same finite **1-600 second** policy as the Cloud Run boundary; alternate service embeddings cannot silently configure an effectively unbounded in-flight provider window.
- Cloud Run checkpoint HMAC keys are bounded to 32-512 UTF-8 bytes and reject boundary whitespace/control characters.
- Evidence-plane readiness cache/backoff policy is finite and bounded: external probe TTL <= 300s, failure backoff <= 300s, stale-readiness grace <= 900s; booleans and NaN/infinity are rejected.

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected platform-specific permission test skipped on Windows.
- Focused core/API/UI suite from the last executable repository run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating the latest activation/checkpoint/readiness/auth/watchdog/bridge/Gemini-boundary hardening.
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

- `build_commander_context()` now rejects boolean/non-numeric/non-finite metric values before any model call while preserving unavailable metric values as explicit JSON null.
- Incident confidence must be a real finite number in [0, 1]; booleans, NaN, infinity, and out-of-range values fail closed before Gemini is invoked.
- Evidence `supports_hypothesis` must be boolean or null rather than arbitrary provider-shaped data.
- The Vertex AI adapter uses `json.dumps(..., allow_nan=False)` and converts serialization failures into a stable StageGuard-owned `Gemini context is not strict JSON` error.
- Focused regressions cover non-finite confidence/evidence, out-of-range confidence, boolean numeric confusion, non-boolean support flags, and explicit null preservation.

### Cloud Run / MCP safety

- Core and Cloud Run remediation execution watchdog policy: 1-600 seconds.
- Checkpoint HMAC key: 32-512 UTF-8 bytes with whitespace/control rejection.
- Hermetic deploy-script regression prevents invalid watchdog values from reaching `gcloud`.
- Private metrics acceptance job identity is selector-safe and bounded before any Cloud Run/Docker action.
- Private metrics bridge upstream timeout is capped at 60 seconds; inbound bearer tokens are capped at 4096 characters and oversized presented candidates are rejected before comparison.
- Grafana MCP smoke has request deadlines, strict JSON-RPC/version/response-ID validation, 1 MiB frame cap, 16-frame pending queue cap, read-only surface enforcement, and image pin regressions.

## Run log — 2026-09-13 — Gemini strict numeric evidence boundary

### Inspected at start

Read this `progress.md` completely before selecting work. Inspected repository metadata/tree, `runtime/gemini_commander.py`, `runtime/investigator.py`, and `runtime/tests/test_gemini_commander.py`. Confirmed the deterministic investigator intentionally emits confidence values in the probability range and `Evidence.value` is modeled as `float | None`. No unrelated repository, cloud resource, Grafana instance, Gemini endpoint, IAM binding, remediation provider, or GitHub Actions workflow was modified or manually triggered.

### Finding

The Gemini advisory boundary claimed to expose a bounded structured projection, but `build_commander_context()` copied metric `Evidence.value` directly and converted `report.confidence` with plain `float(...)`. A manually constructed/corrupted report could therefore put NaN or positive/negative infinity into model context. Python `json.dumps()` permits those values by default and emits non-standard `NaN`/`Infinity` tokens, undermining the strict-JSON contract sent to Vertex AI. The same boundary also did not independently require `supports_hypothesis` to be boolean/null or confidence to remain within [0, 1].

### Exact changes made

1. Added `_finite_number()` in `runtime/gemini_commander.py`; it rejects booleans, non-numeric values, NaN, infinity, and optional range violations while normalizing accepted numbers to `float`.
2. Metric evidence values now pass through that finite-number boundary; `None` remains explicit unavailable evidence rather than being coerced.
3. `supports_hypothesis` is now independently required to be `bool | None` before crossing the model boundary.
4. Incident confidence is now independently constrained to a finite value in the closed interval [0, 1].
5. `_trusted_identifier()` now explicitly checks string type before applying the identifier regex, preserving a StageGuard-owned validation error for malformed custom reports.
6. `GoogleGenAICommanderModel.generate()` now pre-serializes context with `allow_nan=False` and raises the stable `Gemini context is not strict JSON` error if a future caller bypasses the normal context builder with non-JSON-safe content.
7. Extended `runtime/tests/test_gemini_commander.py` with regressions for NaN/+inf/-inf confidence, confidence outside [0, 1], booleans used as numbers, non-finite metric evidence, non-boolean support flags, and null missing-evidence preservation.

Commits:
- `0b36609a6bd326d77d3dfd43ea616ce97f1c4722` — Harden Gemini numeric evidence boundary
- `079152f906ec8683ff460e459581a18fc882e94a` — Add Gemini numeric-boundary regressions

### Checks / results

- Authenticated GitHub connector reads/writes succeeded and both implementation/test commits landed on `UnknownGod2011/Grafana` `main`.
- Re-read the committed `runtime/gemini_commander.py` through the GitHub connector and confirmed the finite-number checks and strict JSON serialization are present.
- Attempted a fresh executable checkout followed by `PYTHONPATH=runtime python -m unittest runtime.tests.test_gemini_commander runtime.tests.test_gemini_acceptance_smoke -v`; the runner failed before checkout with `Could not resolve host: github.com`.
- Therefore the new Gemini regressions did not execute locally in this run and no new green-test claim is made.
- No GitHub Actions workflow was triggered merely to bypass the transient runner DNS failure.

### Decisions

1. Treat confidence as a probability at the model boundary and enforce [0, 1], matching the deterministic investigator's 0.0/0.95/0.97 semantics rather than allowing arbitrary floating-point magnitudes.
2. Preserve `None` for unavailable metric evidence, because absence is meaningful and should remain explicit JSON null rather than becoming 0 or another synthetic value.
3. Reject Python `bool` explicitly even though `bool` is an `int` subclass; `True` must never silently become metric value/confidence 1.0.
4. Keep strict serialization in the Vertex adapter even after builder validation as defense in depth for direct/custom callers.

### Blockers / unknowns

- The new Gemini commander regressions and existing Gemini acceptance smoke need a current executable checkout.
- The metrics-bridge bounds regression and existing bridge suite need a current executable checkout.
- The core watchdog, identity/auth/readiness/remediation/activation/onboarding/Cloud Run focused suites still need a current executable checkout.
- MCP timeout/surface/image-pin regressions still need a current repository run.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- The real disposable private Cloud Run acceptance still requires a private StageGuard service, least-privilege ADC invoker identity, and Docker.
- Historical full-suite failures/errors remain untriaged; there is still no full-suite green claim.

## Single best next step

**As soon as executable checkout works, first run `PYTHONPATH=runtime python -m unittest runtime.tests.test_gemini_commander runtime.tests.test_gemini_acceptance_smoke runtime.tests.test_cloud_run_metrics_bridge_bounds runtime.tests.test_cloud_run_metrics_bridge runtime.tests.test_execution_watchdog_bounds runtime.tests.test_cloudrun_entrypoint -v`; fix any regression immediately. Then run the consolidated identity/auth/readiness/remediation/activation/onboarding/Cloud Run suite. If clean, run MCP timeout/surface/image-pin regressions and the live pinned Grafana MCP 1.4.1 smoke before the private `ADC -> Cloud Run /metrics -> authenticated bridge -> Prometheus up: 1 -> 0 -> 1` acceptance.**

# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the read-only runtime evidence plane. The current vertical slice includes deterministic telemetry, Prometheus/Loki/Grafana, official Grafana MCP access, bounded diagnosis, optional Gemini briefing, revision-bound approval, remediation adapters, telemetry-verified recovery, authenticated lifecycle state, checkpoint/audit integrity, operator UI, Cloud Run deployment hardening, watchdog observability, authenticated metrics bridging, stale/scrape detection, pinned local acceptance images, strict Prometheus/MCP evidence parsing, structured evidence-unavailable abstention, fail-closed operator handling for observability-plane outages, and payload-integrity validation on the private Cloud Run metrics bridge.

Core invariants:
- Grafana/MCP is read-only evidence access; infrastructure write credentials remain isolated.
- Gemini is advisory and cannot mutate diagnosis, approval, remediation, or recovery state.
- Approval is exact-revision-bound and single-use.
- Provider action success never counts as recovery; fresh Grafana telemetry must prove it.
- Durable checkpoint/audit integrity failures fail closed.
- Loss of observability must never be reclassified as a positive remediation deadline breach.
- Ambiguous, malformed, nonnumeric, or non-finite evidence must never be interpreted as healthy evidence.
- Expected evidence-plane transport/protocol failures become sanitized abstention, not diagnosis.
- Programming/configuration defects remain visible exceptions.
- Partial, missing, or unavailable evidence must never reach infrastructure mutation.
- The browser must never turn evidence unavailability into an actionable diagnosis or expose provider failure detail.
- An authenticated HTTP 200 alone is not sufficient bridge readiness; the body must prove it is an unambiguous StageGuard runtime-safety exposition.

## Run log — 2026-09-11 — Cloud Run metrics bridge payload integrity

### Inspected at start

Read `progress.md` completely before deciding what to change. Inspected:
- `runtime/cloud_run_metrics_bridge.py`
- `runtime/tests/test_cloud_run_metrics_bridge.py`
- `runtime/api.py`, including `_service_metrics()` and `/metrics`
- `runtime/tests/test_api.py`
- `runtime/tests/test_api_execution_watchdog.py`
- `docs/runtime-metrics-ingestion.md`
- current `docs/` layout

Also rechecked current official Google Cloud Run service-to-service authentication guidance and current Prometheus configuration documentation. Google continues to document service-to-service Cloud Run authentication using a Google-signed ID token for the receiving service audience, and StageGuard continues to follow that model through ADC rather than storing a static scrape credential.

### Exact changes made

#### Hardened the authenticated metrics bridge against false readiness

Updated `runtime/cloud_run_metrics_bridge.py`.

Previously, `CloudRunMetricsClient.fetch()` treated any bounded HTTP-200 body as a successful StageGuard metrics fetch. That meant an authenticated proxy/login page, comment-only exporter failure, wrong service, or other non-StageGuard body could make bridge `/readyz` report healthy and could be forwarded to Prometheus.

Added `validate_stageguard_metrics()` and a fixed safety sentinel contract:

```text
stageguard_remediation_execution_deadline_exceeded <0|1>
```

An accepted upstream payload must now contain exactly one label-free sample for that metric. Its value must be numeric, finite, and exactly `0` or `1`.

The bridge now rejects:
- empty or comment-only bodies;
- HTML/wrong-service HTTP-200 bodies;
- missing sentinel metrics;
- malformed sentinel lines;
- labeled/spoofed variants instead of the canonical label-free sentinel;
- duplicate/ambiguous sentinel samples;
- nonnumeric values;
- `NaN`, `Inf`, and `-Inf`;
- values outside the boolean gauge domain such as `2`.

Failure still remains sanitized: `/readyz` returns HTTP 503 and bridge `/metrics` returns HTTP 502 without exposing the upstream body, target URL, ID token, ADC detail, or IAM/provider exception.

Commit:
- `ef3e09478121fcf694149e314e683233de1efaee` — harden Cloud Run metrics bridge payload validation

#### Expanded credential-free bridge regressions

Updated `runtime/tests/test_cloud_run_metrics_bridge.py`.

Added coverage for:
- one valid StageGuard sentinel exposition;
- missing/malformed/duplicate/labeled/non-finite/out-of-domain sentinels;
- an HTTP-200 HTML body that must fail client fetch;
- an HTTP-200 non-StageGuard body that must make `/readyz` fail closed;
- continued secret/target sanitization on payload-integrity failure.

Existing target/audience restrictions, timeout validation, bridge-owned authorization, loopback bind safety, liveness/readiness distinction, and upstream-error sanitization remain covered.

Commit:
- `441b20f33ca8258d0ad4d79f31d15a47c5083b31` — add fail-closed metrics bridge payload regressions

#### Added a dedicated production safety contract document

Created `docs/cloud-run-metrics-bridge-safety.md` documenting:
- the Cloud Run/ADC trust model;
- why HTTP 200 is insufficient evidence-plane readiness;
- the exact StageGuard safety sentinel contract;
- fail-closed bridge behavior;
- least-privilege invoker guidance;
- credential-free test coverage;
- the required disposable-project production acceptance sequence.

The doc records official references to Google Cloud Run service-to-service authentication and Prometheus configuration behavior.

Commit:
- `aa83fc21e991400a799fda3d14f005b019b08968` — document authenticated metrics bridge payload safety

### Checks / results

Attempted a fresh executable checkout before making changes:

```bash
git clone --depth 1 https://github.com/UnknownGod2011/Grafana.git /tmp/stageguard
```

The execution container again failed at DNS resolution with:

```text
Could not resolve host: github.com
```

Therefore no claim is made that the updated unittest module, Playwright acceptance, full unittest suite, or Docker rehearsal is green in this run.

Post-write inspection through the connected GitHub integration succeeded and confirmed the new validator is present in the committed bridge implementation.

No GitHub Actions workflow was created, triggered, rerun, or modified. No Grafana Cloud, GCP/IAM/Cloud Run, Gemini, checkpoint, audit, or remediation resource was changed.

### Decisions

1. Treat reachability and payload identity/integrity as separate requirements. An authenticated HTTP 200 is not sufficient readiness.
2. Validate one existing safety-critical StageGuard metric instead of inventing a bridge-only heartbeat that could remain healthy while the real watchdog exposition is broken.
3. Require the canonical label-free sentinel exactly once so duplicate or spoofed/labeled variants fail closed.
4. Keep the validator intentionally narrow rather than reimplementing the Prometheus exposition parser in the bridge.
5. Keep all provider/body details out of bridge failures; payload-validation errors follow the same sanitized boundary as ADC/IAM/network errors.
6. Do not use GitHub Actions merely to compensate for the current container DNS failure.

### Blockers / unknowns

- The updated `runtime/tests/test_cloud_run_metrics_bridge.py` still needs execution in a runnable checkout.
- The Playwright evidence-unavailable browser acceptance still needs execution with Chromium.
- The complete pinned Prometheus 3.13.3 + Grafana 13.2.1 watchdog rehearsal still needs a current run after the latest hardening.
- The authenticated metrics bridge still needs disposable-project acceptance against a private Cloud Run StageGuard service using a dedicated least-privilege invoker identity.
- Historical full-suite failures/errors have not yet been re-triaged; no full-suite green claim exists.

## Single best next step

**Add a bounded, opt-in disposable-project acceptance harness for the private Cloud Run metrics path. It should take an existing service URL and dedicated invoker identity from explicit environment/configuration, verify ADC ID-token acquisition, bridge `/readyz`, bridge `/metrics` sentinel validation, and Prometheus `up == 1`, then provide a non-destructive negative mode that proves an unauthorized/no-token request is rejected. It must never create broad IAM grants, print tokens, mutate StageGuard lifecycle state, or run automatically in CI.**

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected platform-specific permission test skipped on Windows.
- Focused core/API/UI suite from last executable run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, but it predates the latest acceptance hardening.
- Official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0` before the latest evidence-availability changes.
- Incident flow baseline: investigate -> diagnose `uplink-b packet loss` -> exact revision approval -> bounded remediation -> telemetry-verified recovered.

# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the runtime evidence plane. The current vertical slice includes deterministic telemetry, Prometheus/Loki/Grafana, official read-only Grafana MCP access, bounded diagnosis, optional revision-bound Gemini briefing, exact human approval, safe remediation, Grafana-based recovery verification, authenticated lifecycle state, restart reconciliation, operator UI, production deployment hardening, runtime watchdog observability, authenticated Cloud Run metrics ingestion, stale-telemetry detection, a credential-free metrics-outage rehearsal path, pinned Grafana/Prometheus acceptance images, live runtime-version attestation, strict Prometheus safety-query parsing, a live query-local cardinality ambiguity probe, and separate liveness/readiness semantics for the private Cloud Run metrics bridge.

Core invariants:
- Grafana/MCP is read-only evidence access; infrastructure write credentials remain isolated.
- Gemini is advisory and cannot mutate diagnosis, approval, remediation, or recovery state.
- Approval is exact-revision-bound and single-use.
- Provider action success never counts as recovery; fresh Grafana telemetry must prove it.
- Durable checkpoint/audit integrity failures fail closed.
- A healthy watchdog value is trustworthy only while the observability path is delivering fresh samples.
- Loss of observability must never be reclassified as a positive remediation deadline breach.
- Ambiguous, malformed, or non-finite Prometheus safety evidence must never be interpreted as a healthy acceptance signal.
- Metrics bridge process liveness must not be confused with authenticated upstream readiness.

## Run log — 2026-09-11 — authenticated metrics bridge readiness

### Inspected at start

Read `progress.md` completely before deciding what to change. Inspected the current repository and the authenticated metrics path, including:
- `runtime/cloud_run_metrics_bridge.py`
- `runtime/tests/test_cloud_run_metrics_bridge.py`
- `docs/runtime-metrics-ingestion.md`
- the previously recorded watchdog observability acceptance baseline and ambiguity-probe work.

Attempted a fresh local checkout first:

```bash
git clone --depth 1 https://github.com/UnknownGod2011/Grafana.git /tmp/stageguard
```

The execution container still failed with `Could not resolve host: github.com`, so the Docker rehearsal and committed Python test suite could not run from a local checkout in this environment. Work continued through the GitHub repository API instead of stopping on that transient environment limitation.

### Problem identified

The private Cloud Run metrics bridge already had `/healthz`, but that endpoint always returned healthy if the bridge process itself was serving HTTP. It did not prove that:
- Application Default Credentials could mint an ID token;
- the configured audience was accepted;
- the bridge identity had Cloud Run invoke permission;
- the upstream StageGuard service was reachable; or
- authenticated `GET /metrics` actually worked.

Using process liveness as readiness would let an orchestrator or operator see a healthy bridge while every Prometheus scrape was failing.

### Exact changes made

#### Added deep `/readyz` while preserving `/healthz` as liveness

Updated `runtime/cloud_run_metrics_bridge.py`:
- `/healthz` remains a dependency-free process liveness endpoint and returns `200 {"ok":true}` even when the upstream path is broken.
- `/readyz` executes the same `CloudRunMetricsClient.fetch()` path used by Prometheus. This verifies token acquisition, audience/IAM, network reachability, and authenticated access to the fixed upstream `/metrics` endpoint.
- successful readiness returns only `200 {"ok":true,"upstream":"reachable"}`;
- failed readiness returns only `503 {"ok":false,"upstream":"unavailable"}`;
- exceptions are deliberately swallowed at this boundary so target URLs, ID tokens, ADC detail, IAM/provider messages, and upstream bodies cannot leak through readiness responses.
- no generic proxy, remediation, lifecycle, or arbitrary-fetch capability was added.

Commit:
- `84b30264d0a37b375260fffcc3d76c37534dd5ca` — add authenticated metrics bridge readiness probe

#### Added focused bridge regression coverage

Updated `runtime/tests/test_cloud_run_metrics_bridge.py` with cases proving:
- `/healthz` remains 200 when the injected upstream opener fails;
- `/readyz` calls the configured token supplier and the exact fixed `https://<service>/metrics` upstream path;
- readiness uses the bridge-owned Authorization header and configured timeout;
- successful readiness returns the fixed reachable JSON payload;
- failed readiness returns HTTP 503;
- readiness failure bodies do not expose provider exception detail, token contents, or the target hostname;
- existing `/metrics` failure sanitization remains covered.

Commit:
- `4b3ea15b4d0abf6b751d141fb1619d5d5157ee08` — test metrics bridge readiness semantics

#### Documented operational semantics

Updated `docs/runtime-metrics-ingestion.md` to document the distinction:
- `/healthz` is process-only liveness and should not cause restart loops solely because IAM/upstream metrics are unavailable;
- `/readyz` is deep authenticated readiness and intentionally performs a real metrics fetch;
- readiness responses are fixed/sanitized;
- operators should avoid an unnecessarily aggressive readiness cadence because each readiness probe performs a real authenticated upstream request.

Commit:
- `72aaa0b60ff649ba0a401e69b1173801148d4f0e` — document metrics bridge liveness and readiness

### Checks / results

- Re-fetched the committed `runtime/cloud_run_metrics_bridge.py` through the GitHub API and verified the new `_upstream_ready()` helper and `/readyz` branch are present on `main`.
- Re-fetched the committed bridge test module and verified the liveness/readiness/sanitization regression cases are present on `main`.
- Existing target restrictions remain unchanged: HTTPS origin only, no userinfo, arbitrary path, query, or fragment; the forwarded path remains hard-coded to `/metrics`.
- Existing loopback-default listener policy and explicit `--allow-network-bind` requirement remain unchanged.
- The environment could not clone GitHub, so the exact committed unittest module did not execute here and no green claim is made.
- The full Docker observability rehearsal also remains unexecuted in this environment.
- No GitHub Actions workflow was created, modified, triggered, or rerun.
- No external Grafana, Grafana Cloud, GCP, IAM, Cloud Run, Secret Manager, Gemini, checkpoint, or remediation resource was changed.

### Decisions

1. Keep `/healthz` shallow. Dependency failures should not automatically restart-loop a correctly running bridge process.
2. Make `/readyz` deep and fail closed so orchestration/operator readiness reflects the actual authenticated metrics path.
3. Reuse the production `fetch()` path rather than implementing a weaker second authentication probe. Readiness therefore checks the exact operation Prometheus depends on.
4. Keep readiness responses fixed and sanitized instead of exposing diagnostic exception text over HTTP.
5. Do not cache or persist Google ID tokens as part of this change; credential lifecycle remains delegated to ADC/google-auth.

### Blockers / unknowns

- The new bridge tests still need execution from a runnable checkout.
- The complete credential-free Docker watchdog rehearsal still needs to run against the pinned Prometheus 3.13.3 and Grafana 13.2.1 images. It must attest live versions, prove the query-local ambiguity rejection, then prove deadline firing/resolution and stale-telemetry firing/resolution.
- Container digests are still not committed because an authoritative registry digest has not been verified through the available execution path.
- The authenticated metrics bridge still needs one disposable-project acceptance against a private Cloud Run StageGuard service with a least-privilege invoker identity. That live acceptance should now verify `/healthz`, `/readyz`, and `/metrics` separately.
- Cloud Storage Policy Troubleshooter and live Gemini/Vertex acceptance still require authorized disposable-project credentials.

## Single best next step

**Run the complete credential-free Docker observability rehearsal in the first environment with Docker access and a runnable checkout. It must attest Prometheus 3.13.3 and Grafana 13.2.1, prove the live cardinality ambiguity query is rejected, then prove remediation-deadline firing/resolution and stale-telemetry firing/resolution. In the same runnable checkout, execute `python -m unittest runtime.tests.test_cloud_run_metrics_bridge runtime.tests.test_watchdog_ambiguity_probe runtime.tests.test_watchdog_observability_acceptance`.**

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected platform-specific permission test skipped on Windows.
- Focused core/API/UI suite from last executable run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively; it predates the newest watchdog freshness acceptance path, explicit image pins, live runtime-version attestation, strict Prometheus safety-query parsing, the live ambiguity probe, and bridge readiness work.
- Official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`.
- Incident flow baseline: investigate -> diagnose `uplink-b packet loss` -> exact revision approval -> bounded remediation -> telemetry-verified recovered.

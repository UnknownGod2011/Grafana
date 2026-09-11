# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the read-only runtime evidence plane. The current vertical slice includes deterministic telemetry, Prometheus/Loki/Grafana, official Grafana MCP access, bounded diagnosis, optional Gemini briefing, revision-bound approval, remediation adapters, telemetry-verified recovery, authenticated lifecycle state, checkpoint/audit integrity, operator UI, Cloud Run deployment hardening, watchdog observability, authenticated metrics bridging, stale/scrape detection, pinned local acceptance images, strict Prometheus/MCP evidence parsing, structured evidence-unavailable abstention, fail-closed operator handling for observability-plane outages, payload-integrity validation on the private Cloud Run metrics bridge, an opt-in disposable Prometheus acceptance harness for the complete private Cloud Run scrape chain including local bridge failure/recovery, and explicit redirect isolation for Cloud Run identity-token-bearing metrics requests.

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
- The runtime-safety sentinel is label-free by contract; any additional labeled series in that metric family makes the payload ambiguous and must fail closed.
- Cloud Run metrics acceptance must never grant IAM, print credentials, mutate incidents, or require making StageGuard public.
- Recovery acceptance may interrupt only the local metrics bridge; it must not mutate Cloud Run, IAM, or StageGuard lifecycle state.
- An identity-token-bearing Cloud Run metrics request must never follow an HTTP redirect; the configured service origin is the exact credential boundary.

## Run log — 2026-09-11 — Cloud Run redirect credential-boundary hardening

### Inspected at start

Read `progress.md` completely before deciding what to change. Inspected:
- `runtime/cloud_run_metrics_bridge.py`
- `runtime/tests/test_cloud_run_metrics_bridge.py`
- `docs/cloud-run-metrics-bridge-safety.md`
- current `main` head and the previous sentinel-family hardening handoff

Also checked current official documentation for:
- Python `urllib.request` header/redirect semantics;
- Google Cloud Run service-to-service authentication and ID-token audience guidance.

The previous handoff's real Cloud Run acceptance remains blocked in this environment by missing external credentials plus an unrunnable checkout. Rather than stop, this run reviewed the identity-token transport boundary for credential-free production hardening.

### Finding

`CloudRunMetricsClient` previously used `urllib.request.urlopen` as its production opener and supplied the Cloud Run ID token as an ordinary `Request` header.

Python's `urllib.request` follows HTTP redirects by default. Its official documentation specifically notes that headers added normally are also added to redirected requests, and provides `Request.add_unredirected_header()` for headers that must not be added to redirected requests.

StageGuard does not need redirects in this path. The bridge accepts a configured HTTPS service origin and derives the exact `/metrics` URL. Therefore any upstream redirect represents routing/configuration drift or an unexpected intermediary. Following it is both unnecessary and an avoidable credential-boundary risk.

### Exact changes made

#### Hardened production metrics transport

Updated `runtime/cloud_run_metrics_bridge.py`.

Changes:
- added `_RejectRedirectHandler`, which refuses every HTTP redirect;
- added `_open_without_redirects()` and made it the production default opener for `CloudRunMetricsClient`;
- moved the Cloud Run bearer credential from ordinary request headers to `Request.add_unredirected_header()`;
- retained `Accept` and `User-Agent` as ordinary non-secret request headers;
- documented the defense-in-depth model directly in the transport code;
- kept injected openers supported so existing credential-free tests and adapters remain modular.

Commit:
- `eac204551969dcb83249baad86eb594b40133278` — harden Cloud Run metrics redirect boundary

#### Added real redirect-isolation regression

Added `runtime/tests/test_cloud_run_metrics_bridge_redirects.py`.

Coverage proves:
- the bearer token is stored in the request's unredirected-header collection rather than its ordinary header collection;
- a real local redirect server can return `302` pointing to a second local server;
- the production opener raises on the redirect;
- the redirect destination is never contacted;
- the redirect destination therefore cannot receive the credential.

The test's local HTTP servers are intentionally limited to exercising Python redirect mechanics. Production bridge target validation still requires HTTPS.

Commit:
- `c5f062008339c75fadf16cf1213d2cb4442c56e7` — test Cloud Run metrics redirect isolation

#### Documented the credential boundary

Added `docs/cloud-run-metrics-redirect-safety.md` covering:
- why redirects are invalid on the exact Cloud Run metrics path;
- Python's redirect/header behavior;
- the unredirected-header plus no-redirect defense in depth;
- sanitized failure semantics;
- credential-free regression expectations;
- current official Python and Google Cloud references.

Commit:
- `82084c075d979ed486f8d98ab25cf8211ea7aa9e` — document metrics redirect credential boundary

### Checks / results

Re-read the updated bridge from the repository after the write and confirmed the production opener is now redirect-rejecting.

A local isolated Python probe of the same `HTTPRedirectHandler` behavior was executed successfully: a `302` raised `urllib.error.HTTPError` and the destination server observed zero requests. This validates the underlying standard-library behavior used by the regression, but it is not a substitute for running the repository test itself.

Attempted the focused repository test run:

```bash
git clone --depth 1 https://github.com/UnknownGod2011/Grafana.git /tmp/stageguard
cd /tmp/stageguard
python -m unittest \
  runtime.tests.test_cloud_run_metrics_bridge \
  runtime.tests.test_cloud_run_metrics_bridge_redirects \
  runtime.tests.test_cloud_run_metrics_bridge_sentinel_family \
  runtime.tests.test_cloud_run_metrics_acceptance
```

The execution container again failed before checkout with:

```text
Could not resolve host: github.com
```

Therefore no claim is made that the new repository regression or the focused bridge/acceptance suites are green in this run.

No GitHub Actions workflow was created, triggered, rerun, or modified. No GCP/IAM/Cloud Run, Grafana Cloud, Gemini, audit, checkpoint, incident, approval, remediation, or recovery resource was changed.

### Decisions

1. Treat the configured Cloud Run origin as the terminal credential boundary; redirects are invalid rather than something the bridge should normalize or follow.
2. Use two layers: mark the bearer credential unredirected and independently disable redirects in the production opener.
3. Keep redirect failures sanitized at the bridge boundary so routing drift becomes evidence/scrape unavailability, not provider-detail leakage.
4. Preserve opener injection for credential-free tests and modularity.
5. Do not trigger CI merely to work around the execution container's DNS failure.

### Blockers / unknowns

- `runtime/tests/test_cloud_run_metrics_bridge_redirects.py` still needs execution from a real checkout.
- The focused bridge/sentinel-family/acceptance suite still needs execution.
- The real acceptance harness requires an existing private StageGuard Cloud Run test service, working ADC for a least-privilege invoker identity, and Docker.
- The Playwright evidence-unavailable browser acceptance still needs execution with Chromium.
- The complete pinned Prometheus 3.13.3 + Grafana 13.2.1 watchdog rehearsal still needs a current run after the latest hardening.
- Historical full-suite failures/errors have not yet been re-triaged; no full-suite green claim exists.

## Single best next step

**In the first runnable environment, execute the focused bridge redirect/sentinel/acceptance tests, then run `python runtime/cloud_run_metrics_acceptance.py` against a disposable private StageGuard Cloud Run service using a dedicated least-privilege `roles/run.invoker` identity. Confirm that no redirect is required on the real authenticated `/metrics` path and that the complete ADC -> private `/metrics` -> validated bridge -> Prometheus path completes `up: 1 -> 0 -> 1`.**

## Previous run — 2026-09-11 — sentinel-family ambiguity hardening

The private Cloud Run metrics validator was hardened so the canonical label-free safety sentinel cannot coexist with any labeled series using the same metric name. Added `runtime/tests/test_cloud_run_metrics_bridge_sentinel_family.py` to cover bare, labeled, mixed-order, labeled-only, and similarly-prefixed metric cases.

Commits:
- `f9f2d5edb118a43e1701a00a515f907733558fc2` — harden metrics sentinel family validation
- `89bf1a163dd3137910e427b99d9df9f2efe29450` — test metrics sentinel family ambiguity
- `6c5a8e74a949f8b398361e96fb8177fff5208dc3` — record sentinel family hardening progress

That run also attempted the focused checkout/tests but hit the same `Could not resolve host: github.com` environment failure. No CI or external service mutation was performed.

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected platform-specific permission test skipped on Windows.
- Focused core/API/UI suite from last executable run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, but it predates the latest acceptance, sentinel-family, and redirect hardening.
- Official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0` before the latest evidence-availability changes.
- Incident flow baseline: investigate -> diagnose `uplink-b packet loss` -> exact revision approval -> bounded remediation -> telemetry-verified recovered.

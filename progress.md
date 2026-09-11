# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the read-only runtime evidence plane. The current vertical slice includes deterministic telemetry, Prometheus/Loki/Grafana, official Grafana MCP access, bounded diagnosis, optional Gemini briefing, revision-bound approval, remediation adapters, telemetry-verified recovery, authenticated lifecycle state, checkpoint/audit integrity, operator UI, Cloud Run deployment hardening, watchdog observability, authenticated metrics bridging, stale/scrape detection, pinned local acceptance images, strict Prometheus/MCP evidence parsing, structured evidence-unavailable abstention, fail-closed operator handling for observability-plane outages, payload-integrity validation on the private Cloud Run metrics bridge, an opt-in disposable Prometheus acceptance harness for the complete private Cloud Run scrape chain including local bridge failure/recovery, redirect isolation for identity-token-bearing metrics requests, and a same-origin-by-default audience/target credential boundary.

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
- An identity-token-bearing Cloud Run metrics request must never follow an HTTP redirect; the configured service origin is the exact network credential boundary.
- The ID-token audience must match the metrics target origin by default; a different audience is an explicit operator opt-in and must never be accepted silently.

## Run log — 2026-09-11 — Cloud Run audience/target credential-boundary hardening

### Inspected at start

Read `progress.md` completely before deciding what to change. Inspected:
- `runtime/cloud_run_metrics_bridge.py`
- `runtime/tests/test_cloud_run_metrics_bridge.py`
- `runtime/cloud_run_metrics_acceptance.py`
- `docs/cloud-run-metrics-bridge-safety.md`
- the previous redirect/sentinel hardening handoff on `main`

Also checked current official Google Cloud documentation for Cloud Run service identity, service-to-service authentication, configured custom audiences, and ID-token audience semantics.

The previous handoff's disposable Cloud Run acceptance remains blocked here by missing external credentials and an unrunnable checkout. Rather than stop, this run reviewed the pre-request credential configuration boundary.

### Finding

`CloudRunMetricsClient` accepted an explicit `audience` independently from the configured HTTPS metrics target. That allowed a configuration such as:

```text
target   = https://metrics-target.example
audience = https://different-audience.example
```

The client would mint a Google-signed ID token for the second origin and send the bearer credential to the first origin. The token is audience-bound, but silently delivering a freshly minted identity credential to a different network origin is still an unnecessary credential-boundary risk and makes configuration mistakes harder to detect.

Google's current Cloud Run guidance states that the ID-token audience should identify the service being invoked or a configured custom audience. Cloud Run also supports configured custom audiences, including URL-style custom-domain values. Therefore StageGuard can safely prefer target-origin/audience equality and make exceptional cross-origin delivery explicit.

### Exact changes made

#### Hardened `CloudRunMetricsClient`

Updated `runtime/cloud_run_metrics_bridge.py`.

Changes:
- the normalized target origin is now retained as the default and expected audience;
- an explicit audience that differs from the target origin raises `BridgeConfigurationError` by default;
- this failure occurs during client construction, before the token supplier can mint a credential;
- added strict boolean `allow_cross_origin_audience=False` escape hatch for intentionally verified deployments;
- added CLI flag `--allow-cross-origin-audience` so the exception requires an explicit operator acknowledgement;
- preserved all previous HTTPS-origin validation, fixed `/metrics` path, unredirected bearer header, no-redirect transport, bounded body, sentinel validation, and sanitized failure behavior.

Commit:
- `07953ce84a62bc545afda77fe1b5b2af89c093bf` — harden metrics audience credential boundary

#### Added credential-free regression coverage

Added `runtime/tests/test_cloud_run_metrics_bridge_audience_boundary.py`.

Coverage proves:
- default audience equals target origin;
- explicit same-origin audience works without an escape hatch;
- cross-origin audience is rejected by default before `token_supplier()` is called;
- explicit opt-in permits an intentionally different audience while preserving the exact configured target URL;
- the opt-in parameter must be a real boolean rather than a truthy configuration value.

Commit:
- `24828fa273e9b4390f30b7f7c142ac6143455bc5` — test metrics audience credential boundary

#### Documented the boundary

Added `docs/cloud-run-metrics-audience-safety.md` documenting:
- why audience and destination are one credential-delivery trust decision;
- same-origin default behavior;
- fail-before-token-minting semantics;
- when the explicit cross-origin escape hatch may be appropriate;
- preference for a configured Cloud Run custom audience matching the actual target origin;
- interaction with the existing redirect isolation and sentinel-integrity controls;
- official Google Cloud references.

Commit:
- `d89224bfeabc0dd39f7f45a6c765f81b01f05b3a` — document metrics audience credential boundary

### Checks / results

Attempted a clean checkout and focused test run:

```bash
git clone --depth 1 https://github.com/UnknownGod2011/Grafana.git /tmp/stageguard
cd /tmp/stageguard
python -m unittest \
  runtime.tests.test_cloud_run_metrics_bridge_audience_boundary \
  runtime.tests.test_cloud_run_metrics_bridge_redirects \
  runtime.tests.test_cloud_run_metrics_bridge_sentinel_family \
  runtime.tests.test_cloud_run_metrics_bridge
```

The execution container again failed before checkout with:

```text
Could not resolve host: github.com
```

Therefore no claim is made that the new regression or focused bridge suites are green in this run.

No GitHub Actions workflow was created, triggered, rerun, or modified. No GCP/IAM/Cloud Run, Grafana Cloud, Gemini, audit, checkpoint, incident, approval, remediation, or recovery resource was changed.

### Decisions

1. Treat audience/target equality as the safe default because the token's intended recipient and its network recipient should normally be the same origin.
2. Reject a mismatch before token acquisition so an invalid configuration cannot mint a credential as a side effect.
3. Preserve a narrowly named explicit opt-in for legacy or intentionally verified cross-origin deployments rather than banning them outright.
4. Prefer a configured Cloud Run custom audience matching the actual target origin where possible.
5. Keep the disposable acceptance harness fail-closed under the new client rule; it must not silently normalize or bypass an audience mismatch.
6. Do not trigger CI merely to work around the execution container's DNS failure.

### Blockers / unknowns

- `runtime/tests/test_cloud_run_metrics_bridge_audience_boundary.py` still needs execution from a real checkout.
- The redirect/sentinel-family/bridge/acceptance suites still need a current executable run.
- The real acceptance harness requires an existing private StageGuard Cloud Run test service, working ADC for a least-privilege invoker identity, and Docker.
- A deployment that intentionally uses a target origin different from its configured Cloud Run audience now requires explicit `allow_cross_origin_audience=True` / `--allow-cross-origin-audience`; the disposable acceptance harness intentionally does not bypass this automatically.
- The Playwright evidence-unavailable browser acceptance still needs execution with Chromium.
- The complete pinned Prometheus 3.13.3 + Grafana 13.2.1 watchdog rehearsal still needs a current run after the latest hardening.
- Historical full-suite failures/errors have not yet been re-triaged; no full-suite green claim exists.

## Single best next step

**In the first runnable environment, execute the focused audience-boundary + redirect + sentinel + bridge acceptance tests. Then run the disposable private Cloud Run harness with a least-privilege `roles/run.invoker` identity using a target and configured Cloud Run audience that intentionally match. Confirm the complete ADC -> private `/metrics` -> validated bridge -> Prometheus `up: 1 -> 0 -> 1` path remains green without redirect or cross-origin credential delivery.**

## Previous hardening retained

### Cloud Run redirect credential boundary

The bridge installs the bearer credential as an unredirected header and its production opener rejects HTTP redirects. A real local regression requires a redirect destination to receive zero requests and zero credentials.

Commits:
- `eac204551969dcb83249baad86eb594b40133278` — harden Cloud Run metrics redirect boundary
- `c5f062008339c75fadf16cf1213d2cb4442c56e7` — test Cloud Run metrics redirect isolation
- `82084c075d979ed486f8d98ab25cf8211ea7aa9e` — document metrics redirect credential boundary

### Sentinel-family ambiguity hardening

The private Cloud Run metrics validator requires exactly one label-free `stageguard_remediation_execution_deadline_exceeded` sample and rejects any labeled sibling series in that metric family.

Commits:
- `f9f2d5edb118a43e1701a00a515f907733558fc2` — harden metrics sentinel family validation
- `89bf1a163dd3137910e427b99d9df9f2efe29450` — test metrics sentinel family ambiguity

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected platform-specific permission test skipped on Windows.
- Focused core/API/UI suite from last executable run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, but it predates the latest acceptance, sentinel-family, redirect, and audience-boundary hardening.
- Official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0` before the latest evidence-availability changes.
- Incident flow baseline: investigate -> diagnose `uplink-b packet loss` -> exact revision approval -> bounded remediation -> telemetry-verified recovered.

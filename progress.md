# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the read-only runtime evidence plane. The current vertical slice includes deterministic telemetry, Prometheus/Loki/Grafana, official Grafana MCP access, bounded diagnosis, optional Gemini briefing, revision-bound approval, remediation adapters, telemetry-verified recovery, authenticated lifecycle state, checkpoint/audit integrity, operator UI, Cloud Run deployment hardening, watchdog observability, authenticated metrics bridging, stale/scrape detection, strict Prometheus/MCP evidence parsing, structured evidence-unavailable abstention, fail-closed operator handling for observability-plane outages, private Cloud Run scrape acceptance scaffolding, and server/API enforcement preventing Gemini briefing while required evidence is unavailable.

Core invariants:
- Grafana/MCP is read-only evidence access; infrastructure write credentials remain isolated.
- Gemini is advisory and cannot mutate diagnosis, approval, remediation, or recovery state.
- Gemini is not invoked when required observability evidence is unavailable; this is enforced by `IncidentService` and covered at the authenticated HTTP boundary.
- Approval is exact-revision-bound and single-use.
- Provider action success never counts as recovery; fresh Grafana telemetry must prove it.
- Durable checkpoint/audit integrity failures fail closed.
- Loss of observability must never be reclassified as a positive remediation deadline breach.
- Ambiguous, malformed, nonnumeric, or non-finite evidence must never be interpreted as healthy evidence.
- Expected evidence-plane transport/protocol failures become sanitized abstention, not diagnosis.
- Programming/configuration defects remain visible exceptions.
- Partial, missing, or unavailable evidence must never reach infrastructure mutation.
- The browser and HTTP API must never turn evidence unavailability into an actionable diagnosis or expose provider failure detail.
- An authenticated HTTP 200 alone is not sufficient metrics-bridge readiness; the body must prove an unambiguous StageGuard runtime-safety exposition.
- The runtime-safety sentinel is label-free by contract; any additional labeled series in that metric family makes the payload ambiguous and must fail closed.
- Cloud Run metrics acceptance must never grant IAM, print credentials, mutate incidents, or require making StageGuard public.
- Recovery acceptance may interrupt only the local metrics bridge; it must not mutate Cloud Run, IAM, or StageGuard lifecycle state.
- An identity-token-bearing Cloud Run metrics request must never follow an HTTP redirect.
- The ID-token audience must match the metrics target origin by default; a different audience is an explicit operator opt-in.

## Run log — 2026-09-11 — authenticated HTTP fail-closed briefing boundary

### Inspected at start

Read `progress.md` completely before deciding what to change. Inspected:
- `runtime/api.py`, including the authenticated `POST /v1/briefing` route and API error mapping;
- `runtime/incident_service.py`, including the service-level evidence-unavailable briefing guard;
- `runtime/tests/test_api.py` for the existing authenticated HTTP test harness pattern;
- `runtime/tests/test_evidence_unavailable_lifecycle.py` for evidence failure fixtures and service-level assertions;
- `docs/evidence-unavailable-lifecycle.md`.

A clean checkout was attempted first:

```bash
git clone --depth 1 https://github.com/UnknownGod2011/Grafana.git /tmp/stageguard
```

The execution container again failed with `Could not resolve host: github.com`, so repository inspection and writes used the connected GitHub integration.

### Finding

The previous run closed the service-level bypass by making `IncidentService.briefing()` reject a report with non-empty `unavailable_evidence` before Gemini invocation. The authenticated HTTP route delegates to that method, but there was no real-server regression proving a caller bypassing the browser receives the same fail-closed behavior without model invocation, audit mutation, remediation activity, or provider-detail leakage.

### Exact changes made

#### Added authenticated HTTP regression

Created `runtime/tests/test_api_evidence_unavailable_briefing.py`.

The test starts the real StageGuard HTTP server on loopback with `StaticBearerIdentityProvider`, creates an incident whose first causal metric read raises `EvidenceUnavailable`, then performs actual HTTP requests:

1. authenticated `POST /v1/investigate`;
2. authenticated `POST /v1/briefing` for the returned incident id and exact revision.

It asserts:
- investigation returns an `abstain` report with `unavailable_evidence == ["causal"]`;
- briefing returns HTTP 400 with the bounded `invalid_request` envelope;
- the exact safe lifecycle detail is `Gemini briefing is disabled while required incident evidence is unavailable`;
- `Cache-Control: no-store` remains present;
- injected provider-detail and endpoint sentinels are absent from both HTTP response bodies;
- the model `generate()` call count remains zero;
- the audit log remains byte-for-byte/logically unchanged after the rejected briefing;
- the only audit event remains `investigation_completed`;
- the remediation adapter receives zero calls.

Commits:
- `cff9a1d73f2b61cefe01ccee6f8a55cea7fd53dc` — add authenticated HTTP briefing outage regression;
- `fb57a6725d172246711303c1d310106cd4401f4e` — align the assertion with the exact production lifecycle message after inspecting `IncidentService.briefing()`.

#### Updated lifecycle documentation

Updated `docs/evidence-unavailable-lifecycle.md` to document the authenticated `POST /v1/briefing` boundary and the new regression, including no model invocation, no audit mutation, `no-store`, and provider-detail non-disclosure.

Commit:
- `365b5b12b244f81a28aa69cfdbd035f33cd30446` — document HTTP briefing outage regression.

### Checks / results

- Full/focused repository tests could not run because a fresh clone is still blocked by DNS resolution for `github.com`.
- The new Python test source was independently syntax-compiled with `python -m py_compile`; syntax check passed.
- The production error string was re-read directly from `runtime/incident_service.py` before finalizing the HTTP assertion.
- No GitHub Actions workflow was created, modified, triggered, or rerun.
- No GCP/IAM/Cloud Run, Grafana Cloud, Gemini provider, incident, approval, remediation, recovery, checkpoint, or external audit resource was mutated.

No green repository-test claim is made for this run.

### Decisions

1. Test the real HTTP server rather than only `_lifecycle_view` or direct service calls, because the missing assurance was specifically the authenticated API boundary.
2. Reuse the production `make_server` + `StaticBearerIdentityProvider` path so authentication, request parsing, exception mapping, response headers, and serialization are all exercised together.
3. Assert zero model calls and an unchanged audit list so the test proves the rejection occurs before Gemini and does not masquerade as `briefing_failed`.
4. Inject provider-detail sentinels into the evidence exception and assert they never reach HTTP output.
5. Keep the production code unchanged because the service-level guard is already correct; this run closes a verification gap rather than adding duplicate policy logic to the route.
6. Do not trigger CI merely to work around the container DNS failure.

### Blockers / unknowns

- `runtime/tests/test_api_evidence_unavailable_briefing.py` still needs execution from a real repository checkout.
- `runtime/tests/test_evidence_unavailable_lifecycle.py` also still needs a current executable run after the service-level briefing guard.
- The focused Cloud Run audience/redirect/sentinel/bridge acceptance suites need a current executable run.
- The real metrics acceptance harness requires a private StageGuard Cloud Run test service, working ADC for a least-privilege invoker identity, and Docker.
- The Playwright evidence-unavailable browser acceptance still needs execution with Chromium.
- Historical full-suite failures/errors have not yet been re-triaged; no full-suite green claim exists.

## Single best next step

**In the first runnable checkout, execute `runtime.tests.test_evidence_unavailable_lifecycle`, `runtime.tests.test_api_evidence_unavailable_briefing`, and the existing operator evidence-unavailable regressions together. If they pass, resume the disposable private Cloud Run acceptance and prove the real `ADC -> private /metrics -> validated bridge -> Prometheus up: 1 -> 0 -> 1` path.**

## Recent hardening retained

### Server-side evidence-unavailable Gemini guard

`IncidentService.briefing()` rejects a current report with non-empty `unavailable_evidence` before checking/invoking the commander. Rejection creates neither `briefing_generated` nor `briefing_failed` audit state.

Commits:
- `e00214d04dcfe726a317337e1a3512374bdb3be1` — fail closed on Gemini briefing during evidence outage;
- `7367e0bff2e3a0510d1f81e6fc961664be4ac479` — service-level regression;
- `0150e0a3f7fac2619b175ef0079e2d0a9f6a9605` — lifecycle documentation.

### Cloud Run audience/target credential boundary

`CloudRunMetricsClient` requires the ID-token audience to equal the configured metrics target origin by default. Intentional legacy/custom deployments require explicit cross-origin audience opt-in.

Commits:
- `07953ce84a62bc545afda77fe1b5b2af89c093bf`;
- `24828fa273e9b4390f30b7f7c142ac6143455bc5`;
- `d89224bfeabc0dd39f7f45a6c765f81b01f05b3a`;
- `4c53e4976afb699b86aaf7a2b504ed86c0793960`.

### Cloud Run redirect credential boundary

The bridge installs the bearer credential as an unredirected header and rejects HTTP redirects. A local regression requires a redirect destination to receive zero requests and credentials.

Commits:
- `eac204551969dcb83249baad86eb594b40133278`;
- `c5f062008339c75fadf16cf1213d2cb4442c56e7`;
- `82084c075d979ed486f8d98ab25cf8211ea7aa9e`.

### Sentinel-family ambiguity hardening

The private Cloud Run metrics validator requires exactly one label-free `stageguard_remediation_execution_deadline_exceeded` sample and rejects any labeled sibling series using the same metric name.

Commits:
- `f9f2d5edb118a43e1701a00a515f907733558fc2`;
- `89bf1a163dd3137910e427b99d9df9f2efe29450`.

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected platform-specific permission test skipped on Windows.
- Focused core/API/UI suite from last executable run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating the latest acceptance/sentinel/redirect/audience/briefing hardening.
- Official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0` before the latest evidence-availability changes.
- Incident flow baseline: investigate -> diagnose `uplink-b packet loss` -> exact revision approval -> bounded remediation -> telemetry-verified recovered.

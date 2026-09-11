# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the read-only runtime evidence plane. The current vertical slice includes deterministic telemetry, Prometheus/Loki/Grafana, official Grafana MCP access, bounded diagnosis, optional Gemini briefing, revision-bound approval, remediation adapters, telemetry-verified recovery, authenticated lifecycle state, checkpoint/audit integrity, operator UI, Cloud Run deployment hardening, watchdog observability, authenticated metrics bridging, stale/scrape detection, strict Prometheus/MCP evidence parsing, structured evidence-unavailable abstention, fail-closed operator handling for observability-plane outages, private Cloud Run scrape acceptance scaffolding, and server/API enforcement preventing Gemini briefing, approval, or execution from becoming actionable while required evidence is unavailable.

Core invariants:
- Grafana/MCP is read-only evidence access; infrastructure write credentials remain isolated.
- Gemini is advisory and cannot mutate diagnosis, approval, remediation, or recovery state.
- Gemini is not invoked when required observability evidence is unavailable; this is enforced by `IncidentService` and covered at the authenticated HTTP boundary.
- Approval is exact-revision-bound and single-use.
- Only `status="diagnosed"` evidence can become approval material; abstained evidence cannot.
- No execution is possible without a matching explicit approval.
- Provider action success never counts as recovery; fresh Grafana telemetry must prove it.
- Durable checkpoint/audit integrity failures fail closed.
- Loss of observability must never be reclassified as a positive remediation deadline breach.
- Ambiguous, malformed, nonnumeric, or non-finite evidence must never be interpreted as healthy evidence.
- Expected evidence-plane transport/protocol failures become sanitized abstention, not diagnosis.
- Programming/configuration defects remain visible exceptions.
- Partial, missing, or unavailable evidence must never reach infrastructure mutation.
- The browser and HTTP API must never turn evidence unavailability into an actionable diagnosis or expose provider failure detail.
- Rejected evidence-outage briefing/approval/execution requests must not mutate audit state or call Gemini/remediation providers.
- An authenticated HTTP 200 alone is not sufficient metrics-bridge readiness; the body must prove an unambiguous StageGuard runtime-safety exposition.
- The runtime-safety sentinel is label-free by contract; any additional labeled series in that metric family makes the payload ambiguous and must fail closed.
- Cloud Run metrics acceptance must never grant IAM, print credentials, mutate incidents, or require making StageGuard public.
- Recovery acceptance may interrupt only the local metrics bridge; it must not mutate Cloud Run, IAM, or StageGuard lifecycle state.
- An identity-token-bearing Cloud Run metrics request must never follow an HTTP redirect.
- The ID-token audience must match the metrics target origin by default; a different audience is an explicit operator opt-in.

## Run log — 2026-09-11 — authenticated evidence-outage mutation boundary

### Inspected at start

Read `progress.md` completely before deciding what to change. Inspected:
- `runtime/api.py`, including authenticated `POST /v1/approve`, `POST /v1/execute`, error mapping, and `Cache-Control: no-store` behavior;
- `runtime/incident_service.py`, including `briefing()`, `approve()`, and `execute_approved()` lifecycle guards;
- `runtime/tests/test_api_evidence_unavailable_briefing.py` for the current real-server outage test harness;
- `runtime/tests/test_evidence_unavailable_lifecycle.py` from the tests directory inventory;
- `runtime/tests/test_operator_console.py` and `runtime/tests/test_operator_browser_evidence_unavailable.py` from the tests directory inventory;
- `docs/evidence-unavailable-lifecycle.md`.

The connected GitHub integration was available for inspection and writes. A clean executable checkout was also attempted at validation time:

```bash
git clone --depth 1 https://github.com/UnknownGod2011/Grafana.git /tmp/stageguard
```

The execution container still failed with `Could not resolve host: github.com`, so repository execution remained unavailable and no CI workaround was triggered.

### Finding

The previous run proved an authenticated caller cannot bypass the browser and invoke Gemini briefing while evidence is unavailable. `IncidentService.approve()` and `execute_approved()` already fail closed at service level, but there was no real authenticated HTTP regression proving a caller bypassing the UI could not convert an evidence-unavailable abstention into approval or execution state.

That left an important verification gap at the API boundary: route authentication, JSON parsing, exception-to-status mapping, `no-store` headers, response sanitization, audit immutability, remediation-provider inactivity, and final lifecycle state were not exercised together for approval/execution during an observability outage.

### Exact changes made

#### Added authenticated mutation regression

Created `runtime/tests/test_api_evidence_unavailable_mutations.py`.

The test starts the real StageGuard HTTP server on loopback with `StaticBearerIdentityProvider`, creates an incident whose first causal metric read raises `EvidenceUnavailable`, and performs actual authenticated HTTP requests:

1. `POST /v1/investigate`;
2. `POST /v1/approve` with the exact incident id and exact current revision;
3. `POST /v1/execute`;
4. `GET /v1/incident`.

It asserts:
- investigation returns `status="abstain"` with `unavailable_evidence == ["causal"]`;
- the incident initially has no approval and no outcome;
- approval returns HTTP 400 / `invalid_request` with the bounded lifecycle detail `only a diagnosed incident can be approved for remediation`;
- execution returns HTTP 409 / `invalid_state` with the bounded lifecycle detail `matching explicit approval is required before remediation`;
- both rejected mutation responses retain `Cache-Control: no-store`;
- injected provider-detail and private-endpoint sentinels never appear in investigation, mutation, or final incident responses;
- the audit log is unchanged by both rejected mutation attempts;
- the only audit event remains `investigation_completed`;
- Gemini receives zero calls;
- the remediation adapter receives zero calls;
- the final authenticated `GET /v1/incident` still exposes the original abstained revision with no approval and no outcome.

Commit:
- `ae61c10e6e200d5b164b8d8b18c1585733a48ef4` — test fail-closed evidence outage mutations.

#### Updated lifecycle documentation

Updated `docs/evidence-unavailable-lifecycle.md` so the authenticated HTTP contract now explicitly includes approval/execution bypass attempts, not only briefing. The document records that rejected mutation requests are non-authoritative, produce no remediation audit events, call no provider, retain `no-store`, do not disclose provider errors, and leave the incident snapshot unchanged.

Commit:
- `d4c5514b3acf4015b7a77f405bb4795bdfd87e6f` — document fail-closed evidence outage mutations.

### Checks / results

- The new test source was independently syntax-compiled with Python `compile(...)`; syntax validation passed.
- A focused executable suite was attempted with:

```bash
PYTHONPATH=runtime python -m unittest \
  runtime.tests.test_evidence_unavailable_lifecycle \
  runtime.tests.test_api_evidence_unavailable_briefing \
  runtime.tests.test_api_evidence_unavailable_mutations \
  runtime.tests.test_operator_console
```

- That suite could not start because the preceding fresh `git clone` failed DNS resolution for `github.com`.
- No GitHub Actions workflow was created, modified, triggered, or rerun.
- No GCP/IAM/Cloud Run, Grafana Cloud, Gemini provider, incident, approval, remediation, recovery, checkpoint, or external audit resource was mutated.

No green repository-test claim is made for this run.

### Decisions

1. Add a real HTTP mutation regression instead of duplicating policy logic in `api.py`; the service guards are already the source of truth.
2. Use the exact current incident id/revision for the rejected approval attempt so the failure proves status gating, not stale-revision rejection.
3. Attempt execution after the rejected approval so the test proves there is no hidden/partial approval state.
4. Re-read the incident after both rejected mutations to prove state remains abstained with `approval=None` and `outcome=None`.
5. Assert both provider inactivity and audit immutability so a rejection cannot have hidden side effects.
6. Reuse injected provider-error sentinels across all responses to protect the non-disclosure boundary.
7. Avoid CI merely to compensate for transient container DNS failure.

### Blockers / unknowns

- `runtime/tests/test_api_evidence_unavailable_mutations.py` still needs execution from a real repository checkout.
- `runtime/tests/test_api_evidence_unavailable_briefing.py`, `runtime/tests/test_evidence_unavailable_lifecycle.py`, and the operator evidence-unavailable regressions still need a current combined executable run.
- The focused Cloud Run audience/redirect/sentinel/bridge acceptance suites need a current executable run.
- The real metrics acceptance harness requires a private StageGuard Cloud Run test service, working ADC for a least-privilege invoker identity, and Docker.
- The Playwright evidence-unavailable browser acceptance still needs execution with Chromium.
- Historical full-suite failures/errors have not yet been re-triaged; no full-suite green claim exists.

## Single best next step

**In the first runnable checkout, execute the complete evidence-unavailable safety set together: service lifecycle, authenticated briefing, authenticated mutation, operator-console, and Playwright browser regressions. If that set passes, resume the disposable private Cloud Run acceptance and prove the real `ADC -> private /metrics -> validated bridge -> Prometheus up: 1 -> 0 -> 1` path.**

## Recent hardening retained

### Authenticated HTTP evidence-unavailable briefing boundary

A real-server regression proves direct `POST /v1/briefing` cannot bypass the server-side outage guard, invokes Gemini zero times, creates no audit mutation, retains `no-store`, and does not disclose provider-detail sentinels.

Commits:
- `cff9a1d73f2b61cefe01ccee6f8a55cea7fd53dc`;
- `fb57a6725d172246711303c1d310106cd4401f4e`;
- `365b5b12b244f81a28aa69cfdbd035f33cd30446`.

### Server-side evidence-unavailable Gemini guard

`IncidentService.briefing()` rejects a current report with non-empty `unavailable_evidence` before checking/invoking the commander. Rejection creates neither `briefing_generated` nor `briefing_failed` audit state.

Commits:
- `e00214d04dcfe726a317337e1a3512374bdb3be1`;
- `7367e0bff2e3a0510d1f81e6fc961664be4ac479`;
- `0150e0a3f7fac2619b175ef0079e2d0a9f6a9605`.

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
- Historical live Docker rehearsal: PASS twice consecutively, predating the latest acceptance/sentinel/redirect/audience/evidence-outage hardening.
- Official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0` before the latest evidence-availability changes.
- Incident flow baseline: investigate -> diagnose `uplink-b packet loss` -> exact revision approval -> bounded remediation -> telemetry-verified recovered.

# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the read-only runtime evidence plane. The current vertical slice includes deterministic telemetry, Prometheus/Loki/Grafana, official Grafana MCP access, bounded diagnosis, optional Gemini briefing, revision-bound approval, remediation adapters, telemetry-verified recovery, authenticated lifecycle state, checkpoint/audit integrity, operator UI, Cloud Run deployment hardening, watchdog observability, authenticated metrics bridging, stale/scrape detection, pinned local acceptance images, strict Prometheus/MCP evidence parsing, structured evidence-unavailable abstention, fail-closed operator handling for observability-plane outages, payload-integrity validation on the private Cloud Run metrics bridge, an opt-in disposable Prometheus acceptance harness for the complete private Cloud Run scrape chain including local bridge failure/recovery, redirect isolation for identity-token-bearing metrics requests, a same-origin-by-default audience/target credential boundary, and a server-side rule preventing Gemini briefing while required evidence is unavailable.

Core invariants:
- Grafana/MCP is read-only evidence access; infrastructure write credentials remain isolated.
- Gemini is advisory and cannot mutate diagnosis, approval, remediation, or recovery state.
- Gemini is not invoked when required observability evidence is unavailable; this is enforced by `IncidentService`, not only the browser.
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

## Run log — 2026-09-11 — server-side Gemini fail-closed rule for evidence-plane outages

### Inspected at start

Read `progress.md` completely before deciding what to change. Inspected the current repository state and specifically:
- `README.md`
- `runtime/incident_service.py`
- `runtime/investigator.py`
- `runtime/gemini_commander.py`
- `runtime/tests/test_evidence_unavailable_lifecycle.py`
- `docs/evidence-unavailable-lifecycle.md`
- the existing Cloud Run metrics bridge/acceptance handoff

A clean local checkout was attempted first, but the execution container again failed DNS resolution for `github.com`. Repository inspection and edits therefore used the connected GitHub integration.

### Finding

The operator cockpit already disables Gemini briefing when an incident is an `abstain` with `unavailable_evidence`, but `IncidentService.briefing()` itself still allowed a direct API caller to request a briefing for the same incident revision.

That created a server/client policy mismatch. It was also semantically unsafe because the bounded Gemini context intentionally does not include provider errors or unavailable-evidence details. A direct caller could therefore cause an advisory model invocation while StageGuard's authoritative evidence plane was unavailable, even though the browser correctly presented the situation as a fail-closed observability outage.

### Exact changes made

#### Enforced the rule in `IncidentService`

Updated `runtime/incident_service.py` so `briefing()` now rejects a current report with non-empty `unavailable_evidence` before checking/invoking the configured commander.

Behavior:
- the rejection is a deterministic lifecycle `ValueError`;
- Gemini/model code is never invoked;
- no `briefing_generated` event is created;
- no `briefing_failed` event is created, because the model was intentionally not called;
- the existing revision match and checkpoint/audit consistency checks remain in force.

Commit:
- `e00214d04dcfe726a317337e1a3512374bdb3be1` — fail closed on Gemini briefing during evidence outage

A follow-up cleanup restored explanatory comments in unrelated audit-integrity code that were accidentally dropped by the full-file GitHub contents update. The final diff against the previous handoff contains only the intended two-line lifecycle guard in `incident_service.py`.

Cleanup commit:
- `f9e3ea2976747741c5bf569996eadf9461d8c0a5` — restore audit safety commentary

#### Added focused regression coverage

Updated `runtime/tests/test_evidence_unavailable_lifecycle.py` with a `ShouldNotRunModel` fixture and a regression proving:
- an evidence-unavailable incident rejects `service.briefing()`;
- the model's `generate()` method is called zero times;
- the audit log is unchanged by the rejected briefing;
- the only lifecycle event remains `investigation_completed`.

Commit:
- `7367e0bff2e3a0510d1f81e6fc961664be4ac479` — test fail-closed Gemini briefing on evidence outage

#### Documented the server-side policy

Updated `docs/evidence-unavailable-lifecycle.md` to make clear that briefing suppression is enforced at both the browser and service boundary, occurs before model invocation, and is intentionally not recorded as a Gemini failure.

Commit:
- `0150e0a3f7fac2619b175ef0079e2d0a9f6a9605` — document server-side briefing outage guard

### Checks / results

Attempted a fresh executable checkout:

```bash
git clone --depth 1 https://github.com/UnknownGod2011/Grafana.git /tmp/stageguard
```

The environment failed before checkout with:

```text
Could not resolve host: github.com
```

Therefore the focused unittest could not be executed locally in this run and no green test claim is made.

Performed a GitHub compare from the previous handoff (`e12b8182`) to the cleaned implementation (`f9e3ea29`). The resulting code diff is intentionally narrow:
- `runtime/incident_service.py`: +2 lines, 0 deletions;
- `runtime/tests/test_evidence_unavailable_lifecycle.py`: focused regression additions;
- `docs/evidence-unavailable-lifecycle.md`: lifecycle semantics update.

No GitHub Actions workflow was created, modified, triggered, or rerun. No GCP/IAM/Cloud Run, Grafana Cloud, Gemini provider, incident, approval, remediation, recovery, audit backend, or checkpoint resource was mutated.

### Decisions

1. Treat evidence-plane unavailability as deterministic lifecycle state that must be resolved before advisory generation, not as input for Gemini to explain.
2. Enforce the restriction in `IncidentService` so direct API callers cannot bypass browser affordances.
3. Reject before commander invocation so an evidence outage cannot spend model quota or create misleading model-failure audit events.
4. Preserve briefing for other supported deterministic states; this change is narrowly scoped to non-empty `unavailable_evidence` rather than banning all `abstain` briefings.
5. Keep provider error detail out of the model boundary and out of operator-visible state.
6. Do not trigger CI merely to work around the execution container's DNS failure.

### Blockers / unknowns

- `runtime/tests/test_evidence_unavailable_lifecycle.py` needs execution from a real checkout after the new briefing guard.
- The focused Cloud Run audience/redirect/sentinel/bridge acceptance suites still need a current executable run.
- The real metrics acceptance harness requires an existing private StageGuard Cloud Run test service, working ADC for a least-privilege invoker identity, and Docker.
- The Playwright evidence-unavailable browser acceptance still needs execution with Chromium.
- The complete pinned Prometheus 3.13.3 + Grafana 13.2.1 watchdog rehearsal still needs a current run after the latest hardening.
- Historical full-suite failures/errors have not yet been re-triaged; no full-suite green claim exists.

## Single best next step

**In the first runnable environment, execute `runtime.tests.test_evidence_unavailable_lifecycle` together with the existing operator/API evidence-unavailable regressions. Then add an authenticated HTTP-level regression for `POST /v1/briefing` that proves a direct API caller receives the bounded rejection while the commander invocation count and audit timeline remain unchanged. After that, resume the disposable private Cloud Run `ADC -> /metrics -> bridge -> Prometheus up: 1 -> 0 -> 1` acceptance.**

## Recent hardening retained

### Cloud Run audience/target credential boundary

`CloudRunMetricsClient` requires the ID-token audience to equal the configured metrics target origin by default. A mismatch fails during construction before token acquisition. Intentional legacy/custom deployments require explicit `allow_cross_origin_audience=True` / `--allow-cross-origin-audience`.

Commits:
- `07953ce84a62bc545afda77fe1b5b2af89c093bf` — harden metrics audience credential boundary
- `24828fa273e9b4390f30b7f7c142ac6143455bc5` — test metrics audience credential boundary
- `d89224bfeabc0dd39f7f45a6c765f81b01f05b3a` — document metrics audience credential boundary
- `4c53e4976afb699b86aaf7a2b504ed86c0793960` — align metrics bridge safety docs

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
- Historical live Docker rehearsal: PASS twice consecutively, but it predates the latest acceptance, sentinel-family, redirect, audience-boundary, and server-side briefing hardening.
- Official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0` before the latest evidence-availability changes.
- Incident flow baseline: investigate -> diagnose `uplink-b packet loss` -> exact revision approval -> bounded remediation -> telemetry-verified recovered.

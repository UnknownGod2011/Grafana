# StageGuard Progress

## Current status

StageGuard is a personal open-source incident commander for live media workflows. The executable production path now covers:

`strict telemetry mapping → metric/Loki activation pins → official Grafana MCP evidence → deterministic diagnosis + Loki corroboration → authenticated IncidentService → optional revision-bound Gemini briefing → approval-gated remediation → telemetry recovery verification → bounded audit → Cloud Run/IAP deployment → independent liveness/readiness → bounded readiness cache/backoff + StageGuard self-observability → authenticated same-origin operator cockpit`

Core invariants:

- Grafana remains the operational evidence plane; infrastructure write credentials remain separate.
- Production Prometheus and Loki datasource identities and semantic contracts are pinned by expiring activation artifacts.
- Activation freshness and contract/datasource pins are revalidated locally on every readiness request.
- External Grafana MCP readiness probes are bounded and cached so frequent health polling cannot stampede Grafana.
- A previous external success may be reported as `stale` only within a short fixed grace window after a transient refresh failure; once that window expires StageGuard becomes unready.
- A local activation failure is never masked by cached or stale external reachability.
- Gemini remains advisory only and cannot mutate diagnosis, approval, remediation, or recovery state.
- Operator UI requests are same-origin and server-authoritative; the browser receives no Grafana, Gemini, remediation, or infrastructure credential.
- Human approval remains bound to the exact incident evidence revision; the cockpit adds an explicit typed-revision confirmation without weakening server-side enforcement.
- Production writes remain disabled in the standard Cloud Run composition.
- `/healthz` proves process liveness only; `/readyz` proves the bounded evidence plane; `/metrics` exposes fixed, non-sensitive StageGuard readiness telemetry.

## Completed milestones

- Deterministic broadcast telemetry simulator + Prometheus + provisioned Grafana local stack.
- Official Grafana MCP integration with datasource/Prometheus/Loki read tools and writes/proxied tools disabled.
- Deterministic incident investigation and bounded Loki corroboration.
- Strict configurable telemetry mapping, metric preflight, Loki preflight, and expiring activation pins.
- Approval-gated remediation and telemetry-only recovery proof.
- Credential-isolated HTTPS remediation transport.
- Bounded revision-bound Gemini incident-commander briefing layer.
- Verified Google IAP identity provider and bounded Google Cloud Logging audit sink.
- Dedicated non-root Cloud Run image with embedded official Grafana MCP binary and remediation disabled.
- `/healthz` liveness + fail-closed `/readyz` using read-only MCP `get_datasource` checks.
- Persistent readiness probe with external-probe TTL, failure backoff, bounded stale-on-transient-failure semantics, single-flight locking, and Prometheus-format self-observability.
- Authenticated same-origin operator cockpit for deterministic evidence, Gemini briefing, revision-bound approval, execution, and recovery state.

## Run log — 2026-09-07 — authenticated operator cockpit

### Inspected at start

Read `progress.md` completely before choosing work. Then inspected:

- `runtime/api.py`
- `runtime/incident_service.py`
- `runtime/investigator.py`
- `runtime/identity.py`
- `runtime/tests/test_readiness_api.py`
- `README.md`

The highest-value gap matched the previous handoff: StageGuard had a production-capable API and identity boundary but no operator-facing incident cockpit.

### Exact changes made

Added `runtime/operator_console.py`:

- dependency-free HTML/CSS/JavaScript operator cockpit served by StageGuard itself;
- renders incident ID, exact evidence revision, diagnosis status/confidence, production/feed scope, deterministic evidence, approval state, and recovery outcome;
- calls only the existing same-origin authenticated API;
- supports bounded investigation and revision-bound Gemini briefing;
- discards a Gemini briefing client-side if the displayed revision changed while generation was in flight;
- requires the operator to type the complete current revision before the approval control enables, followed by an explicit confirmation dialog;
- exposes execute only when a server-side approval exists and no outcome has consumed it;
- uses DOM `textContent` for dynamic incident/model data and no HTML interpretation;
- uses no localStorage/sessionStorage and embeds no provider credentials, datasource configuration, query language, target, endpoint, or actor field.

Updated `runtime/api.py`:

- serves authenticated `GET /console`, `/assets/operator.css`, and `/assets/operator.js`;
- applies identity validation independently to every cockpit asset request;
- adds strict same-origin CSP for cockpit assets: no default external loads, only self script/style/connect, no forms/base override/framing;
- adds `Referrer-Policy: no-referrer` and `X-Frame-Options: DENY` alongside existing no-store/nosniff response controls;
- leaves `/healthz`, `/readyz`, and `/metrics` platform behavior unchanged;
- increments server version to `StageGuard/0.6`.

Added `runtime/tests/test_operator_console.py`:

- proves cockpit HTML and both static assets require operator authentication;
- proves same-origin CSP/no-store behavior;
- checks that no Grafana/Gemini/bearer credential markers are embedded in browser assets;
- checks exact current-revision binding for Gemini and approval UI logic;
- checks no local/session browser persistence is used;
- confirms `/healthz` and `/metrics` remain independent of operator authentication.

Added `OPERATOR_CONSOLE.md` documenting the operator flow, browser trust boundary, same-origin/IAP composition, CSP, storage policy, and credential-free regression coverage.

Updated `README.md` so the executable vertical slice, safety table, HTTP surfaces, repository map, status, and roadmap all reflect the implemented cockpit rather than listing it as future work.

### Commits produced this run

- `bbc5f0d0` — authenticated StageGuard operator cockpit assets
- `3577ccbc` — authenticated same-origin API serving + browser security headers
- `cea9d68d` — operator cockpit HTTP/security regression coverage
- `0357212b` — operator cockpit security/usage documentation
- `a96eefd6` — initial run handoff
- `94673dce` — README coherence refresh

### Tests / checks / results

Attempted a clean checkout and targeted suite with:

`PYTHONPATH=runtime python -m unittest runtime.tests.test_operator_console runtime.tests.test_readiness_api -v`

The environment failed before Python started because `github.com` DNS resolution is unavailable. The new tests are therefore **not claimed as passing** in this runtime.

No GitHub Actions workflow was created, triggered, rerun, or used as a workaround. No Grafana, Loki, Gemini, IAP, Cloud Logging, Secret Manager, operator, or remediation credential was used. No production Cloud Run or Grafana resource was changed.

### Decisions made

1. **Same process, same origin, same identity boundary.** The cockpit is intentionally not a second frontend service and introduces no browser-side secret boundary.
2. **Browser UX never replaces server authorization.** Typed-revision confirmation improves operator intent while `IncidentService.approve()` remains authoritative.
3. **No third-party frontend dependencies.** This avoids CDN supply-chain exposure and keeps CSP narrow.
4. **No browser persistence.** Incident/model responses are held only in current page memory.
5. **Dynamic values are text only.** No incident or Gemini string is interpreted as HTML.
6. **Production remediation remains disabled in the standard Cloud Run composition.** The cockpit cannot enable it.

### Current blockers / unknowns

- The deterministic Python suite remains unexecuted because this environment cannot resolve `github.com` for a runnable checkout.
- `Dockerfile.api` still needs a real Docker build acceptance on a Docker-capable host.
- The cockpit has not yet been exercised through a real Cloud Run + IAP browser session.
- Cache/stale readiness behavior has not yet been exercised against a real `mcp-grafana:1.3.0` + Grafana Cloud/self-hosted instance.
- Optional Gemini has not yet been exercised against live Vertex AI ADC.

## Single best next step

**Add a bounded incident timeline/audit read model for operators: expose a redacted, incident-scoped lifecycle timeline (investigation → briefing digest/next-step metadata → approval → remediation/recovery) without exposing raw Cloud Logging access or provider strings, render it in the cockpit, and add deterministic pagination/authorization tests. This gives real incident commanders trustworthy provenance while keeping audit storage and credentials server-side.**

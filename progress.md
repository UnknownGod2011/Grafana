# StageGuard Progress

## Current status

StageGuard is a personal open-source incident commander for live media workflows. The executable production path now covers:

`strict telemetry mapping → metric/Loki activation pins → official Grafana MCP evidence → deterministic diagnosis + Loki corroboration → authenticated IncidentService → optional revision-bound Gemini briefing → approval-gated remediation → telemetry recovery verification → bounded durable audit → Cloud Run/IAP deployment → independent liveness/readiness → bounded readiness cache/backoff + self-observability → authenticated same-origin operator cockpit → bounded redacted incident timeline`

Core invariants:

- Grafana remains the operational evidence plane; infrastructure write credentials remain separate.
- Production Prometheus and Loki datasource identities and semantic contracts are pinned by expiring activation artifacts.
- Activation freshness and contract/datasource pins are revalidated locally on every readiness request.
- External Grafana MCP readiness probes are bounded and cached so frequent health polling cannot stampede Grafana.
- A previous external success may be reported as `stale` only within a short fixed grace window after a transient refresh failure; once that window expires StageGuard becomes unready.
- A local activation failure is never masked by cached or stale external reachability.
- Gemini remains advisory only and cannot mutate diagnosis, approval, remediation, or recovery state.
- Operator UI requests are same-origin and server-authoritative; the browser receives no Grafana, Gemini, remediation, Cloud Logging, or infrastructure credential.
- Human approval remains bound to the exact incident evidence revision; the cockpit adds explicit typed-revision confirmation without weakening server-side enforcement.
- Operator audit reads are incident-scoped and derived from a bounded redacted lifecycle projection; the browser never receives generic Cloud Logging read access.
- Production writes remain disabled in the standard Cloud Run composition.
- `/healthz` proves process liveness only; `/readyz` proves the bounded evidence plane; `/metrics` exposes fixed non-sensitive readiness telemetry.

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
- Bounded incident-scoped audit timeline with sequence pagination, actor pseudonymization, event-specific payload allow-lists, and same-origin cockpit rendering.

## Run log — 2026-09-07 — bounded operator audit timeline

### Inspected at start

Read `progress.md` completely before choosing work. Then inspected the current repository and relevant implementation surfaces including:

- `runtime/api.py`
- `runtime/incident_service.py`
- `runtime/operator_console.py`
- `runtime/cloud_audit.py`
- `runtime/tests/test_operator_console.py`
- `OPERATOR_CONSOLE.md`

The highest-value gap matched the previous handoff: lifecycle events were already written to bounded/durable audit sinks, but authenticated incident commanders had no safe incident-scoped provenance view and would otherwise need direct Cloud Logging access.

### Exact changes made

Updated `runtime/incident_service.py`:

- lifecycle events are now also retained in a process-local bounded projection capped at 512 entries;
- `_record()` constructs one canonical `AuditEvent`, appends it to the configured durable audit sink, and only then appends it to the operator projection;
- added `audit_timeline(incident_id, after_sequence, limit)` with exact current-incident binding;
- pagination is deterministic by monotonically increasing audit sequence;
- `after_sequence` must be a non-negative integer and `limit` is hard-bounded to 1..100;
- timeline output contains sequence, timestamp, event type, a 12-character SHA-256-derived pseudonymous actor reference, and an event-specific safe payload allow-list;
- investigation timeline metadata exposes revision/status/confidence/evidence mode while excluding activation identifiers;
- Gemini timeline metadata exposes revision, briefing digest, and bounded next-step classification;
- approval metadata exposes revision and action name while deliberately dropping action target;
- remediation metadata exposes revision, recovery status, sample count, and action acceptance while dropping arbitrary action metadata;
- unknown payload keys are dropped by default, so future audit fields are not automatically exposed to the UI.

Updated `runtime/api.py`:

- added authenticated `GET /v1/audit`;
- query contract is `incident_id` plus optional `after_sequence` and `limit`;
- duplicate, unsupported, malformed, negative, and oversized pagination parameters fail closed;
- the endpoint delegates all incident scoping and output redaction to `IncidentService.audit_timeline()`;
- platform endpoints remain unauthenticated as before, while incident/timeline surfaces require the configured identity provider;
- URL path parsing is now explicit so query strings cannot interfere with endpoint routing;
- server version advanced to `StageGuard/0.7`.

Updated `runtime/operator_console.py`:

- added an incident timeline card to the authenticated same-origin cockpit;
- timeline rows are rendered only with DOM `textContent`;
- pagination uses a 25-event page size and the opaque monotonic sequence cursor supplied by the API;
- timeline data is refreshed after investigation, briefing, approval, and remediation lifecycle transitions;
- no Cloud Logging URL, credential, raw actor identity, provider exception, datasource identifier, query, target, endpoint, or raw evidence is added to browser assets.

Added `runtime/tests/test_audit_timeline.py`:

- verifies deterministic sequence pagination;
- verifies incident scoping;
- verifies 1..100 page bounds and non-negative cursor validation;
- verifies pseudonymous actor references do not expose raw identity;
- verifies activation IDs, target, endpoint, token, and arbitrary payload fields do not escape the allow-list;
- verifies `/v1/audit` requires authentication;
- verifies malformed, ambiguous, unsupported, and unbounded query strings fail with `invalid_request`.

Updated `OPERATOR_CONSOLE.md`:

- documents the timeline HTTP contract and pagination bounds;
- documents the process-local projection vs durable Cloud Logging boundary;
- documents exactly what timeline metadata may and may not reach the browser;
- explicitly states that a process restart empties the operational read projection while durable Cloud Logging remains the audit sink of record.

### Commits produced this run

- `5d80dad4` — bounded incident audit timeline read model
- `f0cd597b` — authenticated `/v1/audit` endpoint
- `02a3cf34` — cockpit timeline rendering
- `1a233899` — authorization/pagination/redaction regression coverage
- `2c65c57d` — operator timeline documentation

### Tests / checks / results

Attempted a clean checkout and targeted suite with:

`PYTHONPATH=runtime python -m unittest runtime.tests.test_audit_timeline runtime.tests.test_operator_console runtime.tests.test_readiness_api -v`

The environment failed before Python started because `github.com` DNS resolution is unavailable to the local execution container. The new tests are therefore **not claimed as passing** in this runtime.

No GitHub Actions workflow was created, triggered, rerun, or used as a workaround. No Grafana, Loki, Gemini, IAP, Cloud Logging, Secret Manager, operator, or remediation credential was used. No production Cloud Run or Grafana resource was changed.

### Decisions made

1. **Do not give the cockpit Cloud Logging query capability.** The runtime keeps a narrow lifecycle projection instead of turning `/v1/audit` into a generic logs proxy.
2. **Allow-list timeline payloads by event type.** New audit fields stay private unless intentionally promoted to the operator contract.
3. **Pseudonymize actor identity.** Operators can correlate repeated lifecycle actions without exposing the raw authenticated subject in browser state.
4. **Keep pagination sequence-based and bounded.** This is deterministic, simple to test, and cannot expand into arbitrary log search.
5. **Treat the process-local timeline as operational context, not durable history.** Cloud Logging remains the durable sink of record.
6. **Preserve remediation safety.** Production remediation remains disabled in the standard Cloud Run composition and the timeline adds no mutation path.

### Current blockers / unknowns

- The deterministic Python suite remains unexecuted because the local execution environment cannot resolve `github.com` for a runnable checkout.
- `Dockerfile.api` still needs a real Docker build acceptance on a Docker-capable host.
- The cockpit has not yet been exercised through a real Cloud Run + IAP browser session.
- Cache/stale readiness behavior has not yet been exercised against a real `mcp-grafana:1.3.0` + Grafana Cloud/self-hosted instance.
- Optional Gemini has not yet been exercised against live Vertex AI ADC.
- The new operator timeline intentionally does not replay durable historical audit entries after a process restart.

## Single best next step

**Make the incident timeline restart-safe without broadening the browser trust boundary: add a narrowly scoped server-side durable audit reader that can reconstruct only `stageguard.audit.v1` entries for one exact incident ID from the dedicated StageGuard Cloud Logging log, enforce strict time/result/page bounds and the same event-field allow-list, keep Cloud Logging credentials server-side, and fall back cleanly to the current in-process projection for local/free development. Add fake-client contract tests before any live Google Cloud exercise.**

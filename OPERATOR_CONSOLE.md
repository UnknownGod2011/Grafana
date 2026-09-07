# StageGuard operator cockpit

StageGuard serves a minimal same-origin operator cockpit at `GET /console` from the existing API process. It is intentionally not a separate frontend service: production identity stays at the existing Google IAP boundary and the browser never needs Grafana, Gemini, remediation, Secret Manager, Cloud Logging, or infrastructure credentials.

## Operator flow

1. Open `/console` through the IAP-protected StageGuard Cloud Run service.
2. Run or refresh the deterministic investigation. The cockpit renders incident ID, evidence revision, status, confidence, production/feed scope, and the bounded evidence slots returned by the authenticated API.
3. Review the incident timeline. StageGuard derives this redacted read model from lifecycle events already emitted by the current process; the browser never queries Cloud Logging directly.
4. Optionally generate a Gemini briefing. The request contains only the current `incident_id` and `revision`; StageGuard discards the response in the browser if the displayed revision changed while generation was in flight.
5. For a diagnosed incident, type the complete current revision into the approval field. The approval button remains disabled until the text exactly matches that revision, then an explicit confirmation is required.
6. Execution is available only after server-side approval exists and no outcome has already consumed it. Recovery state is rendered from the server response; action acceptance is not presented as recovery proof.

## Incident timeline contract

Authenticated operators can request:

`GET /v1/audit?incident_id=<current-id>&after_sequence=<n>&limit=<1..100>`

The endpoint is incident-scoped, sequence-ordered, cursor-paginated, and capped at 100 events per response. StageGuard retains at most 512 lifecycle events in the process-local read model. Durable Cloud Logging remains the audit sink of record; this endpoint deliberately does not become a generic Cloud Logging query proxy.

Timeline entries expose only:

- sequence and timestamp;
- bounded lifecycle event type;
- a 12-character SHA-256-derived pseudonymous actor reference;
- an event-specific allow-list of safe metadata such as evidence revision, diagnosis status/confidence, evidence mode, briefing digest/next-step classification, approved action name, and recovery status/sample count.

The timeline deliberately excludes raw operator identity, Grafana URLs or datasource IDs, activation identifiers, PromQL/LogQL, raw logs/evidence, provider exception strings, remediation targets/endpoints, credentials/tokens, and arbitrary action metadata. Unknown lifecycle event payload fields are dropped by default.

The process-local timeline is operational context, not durable history. A new process starts with an empty read model even though prior durable audit entries remain in Cloud Logging. That boundary avoids granting the StageGuard runtime broad Cloud Logging read/query permission merely to populate the cockpit.

## Browser security boundary

The cockpit is deliberately small and dependency-free:

- `/console`, `/assets/operator.js`, `/assets/operator.css`, `/v1/incident`, and `/v1/audit` all require the configured StageGuard identity provider;
- production deployment therefore relies on the same verified IAP signed assertion as the JSON API;
- the page uses only same-origin API requests and no third-party JavaScript, CSS, fonts, analytics, CDNs, or images;
- a strict CSP permits only same-origin script/style/connect resources and forbids framing, forms, external defaults, and a base URL override;
- responses are `Cache-Control: no-store`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, and `X-Frame-Options: DENY`;
- dynamic incident/model/timeline data is assigned with DOM `textContent`; it is never interpreted as HTML;
- the cockpit uses neither `localStorage` nor `sessionStorage`;
- there is no browser-side Grafana URL/token, Gemini API key, remediation token, datasource UID configuration, PromQL, LogQL, endpoint, action target, Cloud Logging credential, or raw operator identity.

The browser is a presentation and confirmation surface only. Server-side lifecycle validation remains authoritative for revision matching, diagnosis eligibility, approval, single-use execution, audit, and telemetry recovery verification.

## Local testing

A static-bearer deployment can exercise the HTTP assets with an explicit `Authorization` header. For an interactive browser, local development is better run with the loopback development identity provider; never bind that identity mode to a non-loopback interface.

Credential-free regression coverage lives in `runtime/tests/test_operator_console.py` and `runtime/tests/test_audit_timeline.py`. It checks authentication, CSP/no-store behavior, absence of embedded credential markers, exact revision binding, lack of browser persistence, bounded timeline pagination, incident scoping, actor pseudonymization, payload redaction, malformed-query rejection, and independence of `/healthz` and `/metrics`.

# StageGuard operator cockpit

StageGuard serves a minimal same-origin operator cockpit at `GET /console` from the existing API process. It is intentionally not a separate frontend service: production identity stays at the existing Google IAP boundary and the browser never needs Grafana, Gemini, remediation, Secret Manager, or infrastructure credentials.

## Operator flow

1. Open `/console` through the IAP-protected StageGuard Cloud Run service.
2. Run or refresh the deterministic investigation. The cockpit renders incident ID, evidence revision, status, confidence, production/feed scope, and the bounded evidence slots returned by the authenticated API.
3. Optionally generate a Gemini briefing. The request contains only the current `incident_id` and `revision`; StageGuard discards the response in the browser if the displayed revision changed while generation was in flight.
4. For a diagnosed incident, type the complete current revision into the approval field. The approval button remains disabled until the text exactly matches that revision, then an explicit confirmation is required.
5. Execution is available only after server-side approval exists and no outcome has already consumed it. Recovery state is rendered from the server response; action acceptance is not presented as recovery proof.

## Browser security boundary

The cockpit is deliberately small and dependency-free:

- `/console`, `/assets/operator.js`, and `/assets/operator.css` all require the configured StageGuard identity provider;
- production deployment therefore relies on the same verified IAP signed assertion as the JSON API;
- the page uses only same-origin API requests and no third-party JavaScript, CSS, fonts, analytics, CDNs, or images;
- a strict CSP permits only same-origin script/style/connect resources and forbids framing, forms, external defaults, and a base URL override;
- responses are `Cache-Control: no-store`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, and `X-Frame-Options: DENY`;
- dynamic incident/model data is assigned with DOM `textContent`; it is never interpreted as HTML;
- the cockpit uses neither `localStorage` nor `sessionStorage`;
- there is no browser-side Grafana URL/token, Gemini API key, remediation token, datasource UID configuration, PromQL, LogQL, endpoint, action target, or operator identity field.

The browser is a presentation and confirmation surface only. Server-side lifecycle validation remains authoritative for revision matching, diagnosis eligibility, approval, single-use execution, audit, and telemetry recovery verification.

## Local testing

A static-bearer deployment can exercise the HTTP assets with an explicit `Authorization` header. For an interactive browser, local development is better run with the loopback development identity provider; never bind that identity mode to a non-loopback interface.

Credential-free regression coverage lives in `runtime/tests/test_operator_console.py` and checks authentication, CSP/no-store behavior, absence of embedded credential markers, exact revision binding, lack of browser persistence, and independence of `/healthz` and `/metrics`.

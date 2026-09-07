# StageGuard operator cockpit

StageGuard serves a minimal same-origin operator cockpit at `GET /console` from the existing API process. It is intentionally not a separate frontend service: production identity stays at the existing Google IAP boundary and the browser never needs Grafana, Gemini, remediation, Secret Manager, Cloud Logging, or infrastructure credentials.

## Operator flow

1. Open `/console` through the IAP-protected StageGuard Cloud Run service.
2. Run or refresh the deterministic investigation. The cockpit renders incident ID, evidence revision, status, confidence, production/feed scope, and the bounded evidence slots returned by the authenticated API.
3. Review the incident timeline. In production StageGuard merges the process-local lifecycle projection with a narrowly scoped durable read from the dedicated StageGuard Cloud Logging log; the browser never queries Cloud Logging directly.
4. Optionally generate a Gemini briefing. The request contains only the current `incident_id` and `revision`; StageGuard discards the response in the browser if the displayed revision changed while generation was in flight.
5. For a diagnosed incident, type the complete current revision into the approval field. The approval button remains disabled until the text exactly matches that revision, then an explicit confirmation is required.
6. Execution is available only after server-side approval exists and no outcome has already consumed it. Recovery state is rendered from the server response; action acceptance is not presented as recovery proof.

## Incident timeline contract

Authenticated operators can request:

`GET /v1/audit?incident_id=<current-id>&after_sequence=<n>&limit=<1..100>`

The endpoint is incident-scoped, sequence-ordered, cursor-paginated, and capped at 100 events per response. StageGuard retains at most 512 lifecycle events in the process-local read model.

When the runtime uses `--audit-backend cloud-logging`, it also constructs a server-side `GoogleCloudAuditReader`. That reader is intentionally narrower than a generic Logging client:

- it is bound to the exact configured StageGuard log via its fully qualified `logName`;
- it requires `jsonPayload.schema="stageguard.audit.v1"`;
- it filters one exact incident ID and only sequences greater than the supplied cursor;
- it applies a fixed 24-hour lookback by default, with a hard implementation ceiling of seven days;
- it caps a single provider read at 101 entries so the service can fetch at most one look-ahead row for pagination;
- it re-validates every returned structured document using the same audit-v1 shape/size/payload constraints used by the write path;
- it rejects unexpected top-level fields, wrong-incident entries, out-of-window timestamps, lower-bound sequence violations, and conflicting duplicate sequences.

The service merges durable and process-local events by sequence, fails closed if two different events claim the same sequence, then applies the same event-specific UI allow-list. The Cloud Logging credential remains server-side and `/v1/audit` never accepts arbitrary Logging filters, resource names, time ranges, log names, or query expressions.

Timeline entries expose only:

- sequence and timestamp;
- bounded lifecycle event type;
- a 12-character SHA-256-derived pseudonymous actor reference;
- an event-specific allow-list of safe metadata such as evidence revision, diagnosis status/confidence, evidence mode, briefing digest/next-step classification, approved action name, and recovery status/sample count.

The timeline deliberately excludes raw operator identity, Grafana URLs or datasource IDs, activation identifiers, PromQL/LogQL, raw logs/evidence, provider exception strings, remediation targets/endpoints, credentials/tokens, and arbitrary action metadata. Unknown lifecycle event payload fields are dropped by default.

Local/free development continues to use the process-local projection with the JSONL sink and requires no Cloud Logging read permission. Production Cloud Logging mode can reconstruct durable entries for the exact current incident instead of relying only on events retained by one process. This does not restore the complete incident state machine after a cold restart; full lifecycle checkpoint/recovery remains a separate concern.

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

Credential-free regression coverage lives in `runtime/tests/test_operator_console.py`, `runtime/tests/test_audit_timeline.py`, and `runtime/tests/test_durable_audit_reader.py`. It checks authentication, CSP/no-store behavior, absence of embedded credential markers, exact revision binding, lack of browser persistence, bounded timeline pagination, incident scoping, actor pseudonymization, payload redaction, malformed-query rejection, durable query bounds/log pinning/document validation, durable/local merge conflict handling, and independence of `/healthz` and `/metrics`.

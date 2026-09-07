# StageGuard Progress

## Current status

StageGuard is a personal open-source incident commander for live media workflows. The executable path covers strict telemetry mapping, metric/Loki activation pins, official Grafana MCP evidence, deterministic diagnosis with Loki corroboration, authenticated incident lifecycle orchestration, optional revision-bound Gemini briefing, approval-gated remediation, Grafana recovery verification, bounded durable audit reconstruction, signed GCS incident checkpoints with strict generation CAS, checkpoint observability, fail-closed conflict recovery, remediation execution-uncertainty recovery, Cloud Run/IAP deployment, operator liveness/readiness/self-observability, and a same-origin operator cockpit with restart-safe lifecycle recovery guidance.

Core invariants:

- Grafana remains the operational evidence plane; infrastructure write credentials remain separate.
- Gemini is advisory only and cannot mutate diagnosis, approval, remediation, or recovery state.
- Human approval is single-use and bound to the exact deterministic evidence revision.
- Fresh investigation clears prior approval/outcome before persisting the new revision.
- Restored checkpoints must match configured telemetry scope and recompute to the persisted evidence revision.
- Production GCS checkpoints require HMAC-SHA-256 authenticity plus strict pinned-generation compare-and-swap.
- Generation conflicts fail closed; losing state is never merged or retried automatically.
- A CAS conflict after remediation contact is execution ambiguity and remains unready until durable-winner reload, provider reconciliation where required, and fresh Grafana evidence.
- Reconciliation never replays remediation; the deterministic operation id remains server-owned and is never accepted from the browser/API caller.
- Provider metadata, credentials, Gemini output, Grafana secrets, checkpoint signing material, and provider reconciliation detail are not exposed to the browser.
- `/healthz` proves process liveness only; `/readyz` proves bounded evidence-plane and lifecycle consistency.

## Completed milestones

- Deterministic broadcast telemetry simulator + Prometheus + provisioned Grafana local stack.
- Official Grafana MCP integration with datasource/Prometheus/Loki read tools and write/proxy tools disabled.
- Deterministic incident investigation and bounded Loki corroboration.
- Strict configurable telemetry mapping, metric/Loki preflight, and expiring activation pins.
- Approval-gated remediation and Grafana telemetry-only recovery proof.
- Credential-isolated HTTPS production remediation transport with deterministic idempotency identity.
- Bounded revision-bound Gemini incident-commander briefing layer.
- Verified Google IAP identity provider and bounded Cloud Logging audit sink/reader.
- Dedicated non-root Cloud Run image with embedded official Grafana MCP binary and remediation disabled by default.
- `/healthz`, fail-closed `/readyz`, readiness caching/backoff, and Prometheus-format self-observability.
- Authenticated same-origin operator cockpit and bounded audit timeline.
- Signed GCS lifecycle checkpoints with strict generation CAS, conflict metrics, explicit winner reload, and fail-closed remediation execution uncertainty.
- Restart-safe operator recovery UX exposing only `clear`, `reload_required`, or `reloaded`.
- Provider-neutral, read-only HTTP idempotency reconciliation transport contract with bounded result states.

## Run log — 2026-09-08 — read-only remediation reconciliation transport

### Inspected at start

Read `progress.md` completely before deciding what to change. Then inspected:

- repository metadata/default branch and current head (`f92bab4044af69595e7f3b6e56ef84ef9d44c255` at run start);
- `runtime/execution_safety.py`;
- `runtime/production_remediation.py`;
- `runtime/http_remediation_transport.py`;
- `runtime/tests/test_http_remediation_transport.py`;
- `runtime/tests/test_production_remediation.py`;
- `runtime/bootstrap.py` and `runtime/tests/test_bootstrap.py`.

The highest-value gap matched the prior handoff: `AllowlistedProductionRemediationClient` correctly required provider reconciliation after ambiguous execution, but the default HTTPS transport offered no read-only idempotency lookup, leaving real production recovery permanently fail-closed after that race.

### Exact changes made

Updated `runtime/http_remediation_transport.py`:

- added optional deployment-owned `reconciliation_endpoint` configuration;
- validates both execution and reconciliation endpoints as absolute credential-free HTTPS URLs with no query/fragment components;
- added `reconcile(operation_id, timeout_seconds=...)` as a GET-only lookup;
- request URL contains only the URL-encoded deterministic StageGuard operation id;
- reconciliation sends no body, action, production id, target, incident evidence, approval, or replayable command payload;
- requires an exact bounded JSON response containing only `operation_id` and `state`;
- accepts only `accepted` and `not_found` states;
- maps 404 to `not_found`;
- maps timeout, network errors, non-404 HTTP errors, oversized responses, malformed JSON, extra fields, unknown states, and wrong operation-id echoes to `unknown`;
- missing reconciliation configuration remains intentionally fail-closed as `unknown`;
- execution semantics and existing bounded retry behavior were not changed.

Updated `runtime/tests/test_http_remediation_transport.py`:

- validates reconciliation endpoint HTTPS requirements;
- proves reconciliation uses GET with no request body;
- proves only the server-owned operation id appears in the lookup request and action/production/target do not;
- covers `accepted` and 404→`not_found` behavior;
- covers timeout/network failures, malformed documents, wrong operation-id echo, extra fields, unknown provider states, and oversized response fail-closed behavior;
- proves missing reconciliation configuration and malformed operation ids perform no network call.

Added `REMEDIATION_RECONCILIATION.md` documenting the provider-neutral contract, redaction/safety properties, and remaining bootstrap wiring gap.

### Commits produced this run

- `cfd2b7d0` — add read-only remediation reconciliation transport

### Tests / checks / results

No GitHub Actions workflow was intentionally triggered, rerun, or modified.

The repository was changed through the authenticated GitHub connector. This environment still does not provide a reliable direct checkout/executable path for the repository, so the Python suite is **not claimed as executed successfully** in this run.

No Grafana, Loki, Gemini, IAP, Cloud Logging, GCS, Secret Manager, operator, or remediation credential/resource was used.

### Decisions made

1. **Reconciliation is a lookup, never a command.** The reference transport uses GET and has no body, eliminating any accidental command replay semantics.
2. **Execution and reconciliation endpoints remain separate.** Deployments can independently authorize command execution and idempotency lookup.
3. **Provider detail is aggressively collapsed.** Only `accepted`, `not_found`, or `unknown` enter the service boundary; all ambiguous cases remain `unknown`.
4. **404 is the only transport-level negative proof.** Other non-success statuses do not imply absence and therefore remain `unknown`.
5. **Missing reconciliation configuration stays fail-closed.** Existing deployments do not become less safe merely by upgrading.

### Current blockers / unknowns

- The deterministic Python suite remains unexecuted in this environment.
- Production bootstrap does not yet pass a reconciliation endpoint into `HttpRemediationTransport`; explicit production remediation therefore remains deliberately blocked after ambiguous execution until that wiring is added.
- End-to-end `ExecutionSafeIncidentService` coverage with the concrete HTTP reconciliation transport should be added after bootstrap wiring.
- Real-GCS two-instance acceptance, Cloud Run/IAP browser acceptance, and real Grafana MCP metric+Loki acceptance still require external credentials/resources.

## Single best next step

**Wire a dedicated `STAGEGUARD_REMEDIATION_RECONCILIATION_ENDPOINT` into production bootstrap, require/validate it whenever explicit production remediation is enabled, and add bootstrap plus execution-safety tests proving `accepted`, `not_found`, timeout/error, malformed-response, and repeated reconciliation never replay remediation.**

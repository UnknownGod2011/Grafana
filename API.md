# StageGuard HTTP API contract

StageGuard exposes a deliberately small HTTP surface. Platform probes are unauthenticated and operator surfaces require the configured identity provider. The browser and callers never provide Grafana queries, datasource identifiers, remediation action names, targets, provider operation IDs, credentials, checkpoint locations, or operator identity in request JSON.

## Platform surfaces

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/healthz` | Process liveness only. A `200` does not imply evidence-plane or lifecycle readiness. |
| `GET` | `/readyz` | Evidence-plane and lifecycle-safety readiness. Returns `503` when fail-closed interlocks are active. |
| `GET` | `/metrics` | Fixed-cardinality, non-secret Prometheus telemetry for StageGuard runtime health and lifecycle safety. |

## Authenticated read surfaces

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/console` | Same-origin operator cockpit. |
| `GET` | `/assets/operator.css` | Cockpit stylesheet. |
| `GET` | `/assets/operator.js` | Cockpit JavaScript. |
| `GET` | `/v1/incident` | Current bounded lifecycle view, including checkpoint, audit-integrity, execution-reconciliation, watchdog, and recovery state. |
| `GET` | `/v1/audit?incident_id=...&after_sequence=...&limit=...` | Bounded incident-scoped audit timeline. |

## Authenticated lifecycle mutations

All mutation endpoints derive actor identity from the configured identity provider. Unless stated otherwise, bodies must be JSON objects and unsupported fields are rejected.

| Method | Path | Accepted body | Contract |
|---|---|---|---|
| `POST` | `/v1/investigate` | `{}` | Collect the pinned Grafana evidence profile and produce a deterministic diagnosis or abstention. |
| `POST` | `/v1/briefing` | `{"incident_id":"...","revision":"..."}` | Generate an advisory Gemini briefing bound to the exact current evidence revision. Gemini cannot approve or mutate infrastructure. |
| `POST` | `/v1/approve` | `{"incident_id":"...","revision":"..."}` | Record explicit human approval for exactly one current evidence revision. |
| `POST` | `/v1/execute` | `{}` | Execute the already-approved bounded remediation once. Action acceptance is not recovery; fresh Grafana telemetry must verify recovery. |
| `POST` | `/v1/recovery/recheck` | `{}` | Re-run recovery verification after an accepted action ended as `recovery_unverified`. This path has no remediation client and cannot redispatch the provider mutation. |
| `POST` | `/v1/checkpoint/reload` | `{}` | Reload and validate the durable checkpoint winner after a compare-and-swap conflict. This does not execute remediation. |
| `POST` | `/v1/execution/reconcile` | `{}` | Reconcile an ambiguous previously-dispatched idempotent provider operation through the server-owned reconciliation path, then require fresh Grafana evidence. Callers cannot supply an operation ID or provider state. |

## No-replay execution-uncertainty workflow

A remediation provider may accept an operation immediately before the final lifecycle checkpoint loses compare-and-swap. StageGuard treats this as `execution_uncertain`: the provider side effect may already have happened, so retrying `/v1/execute` would be unsafe.

The safe operator workflow is:

1. Read `GET /v1/incident` and confirm the server reports an execution-safety interlock.
2. If the server reports `execution_reconciliation_state=reload_required`, call `POST /v1/checkpoint/reload` with `{}`.
3. Call `POST /v1/execution/reconcile` with `{}`. The deterministic StageGuard operation reference remains server-owned; the request cannot substitute it.
4. StageGuard reconciles the provider idempotency record without sending another remediation command.
5. A successful bounded reconciliation performs a fresh Grafana investigation. Any later remediation therefore requires a new evidence revision and a new human approval.

Never use `/v1/execute` to recover from `execution_uncertain` or from `recovery_unverified`.

## Recovery-only workflow

When the remediation provider explicitly accepted the action but the bounded verification window did not prove recovery, StageGuard persists `recovery_unverified`. The consumed approval must not be reused.

`POST /v1/recovery/recheck` is the only follow-up mutation for that state. It reads fresh pinned Grafana recovery evidence and can promote the same incident revision to `recovered`; it has no provider-write adapter and therefore cannot replay the external side effect.

## Authentication and request safety

Production operator surfaces are intended to sit behind the configured production identity provider (for example the verified Google IAP assertion path used by the Cloud Run composition). Local loopback development may use the development identity provider; non-loopback binds reject development-only identity.

Mutation request framing is deliberately stricter than generic HTTP interoperability. StageGuard does not implement request transfer coding, so any `Transfer-Encoding` field is rejected before body bytes are read. `Content-Length` may appear at most once; duplicate values are rejected even when identical. This avoids proxy/origin parser differentials and ensures ambiguous framing cannot reach a lifecycle mutation. A missing `Content-Length` is treated as an empty body, while non-empty bodies remain capped by `MAX_BODY_BYTES` and must be JSON objects.

The API caps JSON bodies, rejects unsupported fields, uses same-origin cockpit requests, and returns bounded error messages. Sensitive provider responses, credentials, raw PromQL/LogQL, arbitrary targets, and infrastructure endpoints are not accepted through this API surface.

## Related design documents

- `OPERATOR_CONSOLE.md` — browser/operator behavior and recovery controls.
- `EXECUTION_UNCERTAINTY.md` — durable dispatch barrier, reconciliation state machine, and restart safety.
- `INCIDENT_CHECKPOINTS.md` — durable lifecycle checkpoint schema and restore rules.
- `OPERATIONS_AND_SAFETY.md` — deployment and operational safety model.

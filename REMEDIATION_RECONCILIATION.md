# Production Remediation Reconciliation

StageGuard treats a checkpoint compare-and-swap loss after a remediation provider was contacted as **execution uncertainty**. It must not replay that action. Instead, the server-owned deterministic operation id is reconciled against the provider's idempotency record, then StageGuard performs a fresh Grafana investigation before any new approval can be issued.

## HTTP contract

`HttpRemediationTransport` supports an optional, deployment-owned reconciliation endpoint separate from the execution endpoint.

Given a configured base such as:

```text
https://writer.example/v1/operations
```

StageGuard performs exactly:

```text
GET /v1/operations/<operation-id>
Authorization: Bearer <deployment-owned credential>
Accept: application/json
```

There is no request body. The lookup does not send the remediation action, production id, target, previous approval, incident evidence, or any replayable command payload.

A successful lookup must return exactly:

```json
{"operation_id":"sg-...","state":"accepted"}
```

or:

```json
{"operation_id":"sg-...","state":"not_found"}
```

A 404 response is treated as `not_found`. Every other HTTP failure, timeout, network failure, oversized response, malformed JSON document, wrong operation-id echo, additional response field, or unknown state fails closed to `unknown`.

## Safety properties

- Reconciliation is read-only and GET-only.
- Operation ids are generated and retained by StageGuard; callers never submit them through the StageGuard API or cockpit.
- The reconciliation URL and bearer credential are deployment configuration, not incident input.
- Reconciliation does not retry remediation and never calls the execution endpoint.
- Provider result details are collapsed to `accepted`, `not_found`, or `unknown`; only the higher-level `reload_required` / `reloaded` / `clear` phase is exposed to the operator cockpit.
- `unknown` keeps StageGuard blocked and unready.
- Even `accepted` or `not_found` is insufficient to restore normal lifecycle operation: StageGuard still requires a fresh Grafana investigation, which invalidates the stale approval and outcome.

## Deployment wiring status

The transport contract and credential-free regression coverage exist. The production bootstrap still constructs `HttpRemediationTransport` with only its execution endpoint and credential, which intentionally leaves reconciliation unavailable and therefore fail-closed after ambiguous execution.

The next production wiring step is to add a dedicated environment variable such as `STAGEGUARD_REMEDIATION_RECONCILIATION_ENDPOINT`, validate it as an absolute credential-free HTTPS URL before runtime startup, and pass it into `HttpRemediationTransport` only when explicit production remediation is enabled.

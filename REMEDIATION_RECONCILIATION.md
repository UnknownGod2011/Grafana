# Production Remediation Reconciliation

StageGuard treats a checkpoint compare-and-swap loss after a remediation provider was contacted as **execution uncertainty**. It must not replay that action. Instead, the server-owned deterministic operation id is reconciled against the provider's idempotency record, then StageGuard performs a fresh Grafana investigation before any new approval can be issued.

## HTTP contract

`HttpRemediationTransport` uses a deployment-owned reconciliation endpoint separate from the execution endpoint for explicit production remediation.

Given a configured base such as:

```text
https://reader.example/v1/operations
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

## Production configuration

Explicit production remediation now requires all three settings:

```text
STAGEGUARD_REMEDIATION_ENDPOINT=https://writer.example/v1/recover
STAGEGUARD_REMEDIATION_RECONCILIATION_ENDPOINT=https://reader.example/v1/operations
STAGEGUARD_REMEDIATION_TOKEN=<deployment-owned-secret>
```

Both endpoints are validated as absolute, credential-free HTTPS URLs with no query or fragment. Missing or invalid reconciliation configuration prevents production remediation startup rather than allowing a deployment that cannot safely resolve execution ambiguity.

The CLI exposes `--remediation-reconciliation-endpoint-env` so deployments can rename the environment variable without turning endpoint values into command-line arguments.

## Safety properties

- Reconciliation is read-only and GET-only.
- Operation ids are generated and retained by StageGuard; callers never submit them through the StageGuard API or cockpit.
- Execution and reconciliation URLs are separate deployment configuration, not incident input.
- Reconciliation does not retry remediation and never calls the execution endpoint.
- Provider result details are collapsed to `accepted`, `not_found`, or `unknown`; only the higher-level `reload_required` / `reloaded` / `clear` phase is exposed to the operator cockpit.
- `unknown` keeps StageGuard blocked and unready.
- Even `accepted` or `not_found` is insufficient to restore normal lifecycle operation: StageGuard still requires a fresh Grafana investigation, which invalidates the stale approval and outcome.

## Remaining acceptance work

Credential-free unit coverage verifies bootstrap requires and propagates the dedicated reconciliation endpoint. Full production acceptance still requires the executable Python suite plus real deployment tests for the provider idempotency service, GCS checkpoint races, Grafana MCP evidence refresh, and Cloud Run/IAP identity.

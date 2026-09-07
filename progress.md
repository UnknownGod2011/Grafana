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
- Explicit production remediation now requires and wires a dedicated read-only reconciliation endpoint.

## Run log — 2026-09-08 — production reconciliation bootstrap wiring

### Inspected at start

Read `progress.md` completely before deciding what to change. Then inspected:

- repository metadata/default branch;
- `runtime/bootstrap.py`;
- `runtime/tests/test_bootstrap.py`;
- `runtime/http_remediation_transport.py`;
- `runtime/production_remediation.py`;
- `REMEDIATION_RECONCILIATION.md`.

The highest-value gap matched the prior handoff: the concrete HTTPS transport already supported read-only provider idempotency lookup, but the production bootstrap did not pass a reconciliation endpoint into it. A real deployment could therefore execute remediation but remain permanently fail-closed after an ambiguous post-provider checkpoint CAS race.

### Exact changes made

Updated `runtime/bootstrap.py`:

- added `remediation_reconciliation_endpoint_env`, defaulting to `STAGEGUARD_REMEDIATION_RECONCILIATION_ENDPOINT`;
- explicit production remediation now requires that environment variable in addition to the execution endpoint and bearer credential;
- passes the dedicated endpoint to `HttpRemediationTransport(reconciliation_endpoint=...)`;
- added CLI option `--remediation-reconciliation-endpoint-env` so deployments can rename the environment variable without putting an endpoint value directly on the command line;
- retained the existing prohibition on explicit production remediation for the demo telemetry profile;
- retained separation between custom `remediation_factory` and explicit production remediation.

Added `runtime/tests/test_production_reconciliation_bootstrap.py`:

- verifies explicit production remediation fails closed when the reconciliation endpoint is absent;
- verifies the execution and reconciliation endpoints are wired separately into the concrete HTTP transport;
- verifies an insecure HTTP reconciliation endpoint is rejected before any network call.

Updated `REMEDIATION_RECONCILIATION.md`:

- documents the now-required production environment variable;
- documents separate writer/read endpoint examples;
- documents CLI environment-variable indirection;
- removes the stale statement that production bootstrap wiring remained incomplete.

### Commits produced this run

- `bc69f7ac` — wire production remediation reconciliation endpoint
- `1fedeba7` — test production reconciliation bootstrap wiring
- `12c4b5ae` — document production reconciliation bootstrap wiring

### Tests / checks / results

Attempted a credential-free local validation with:

```text
python -m unittest tests.test_production_reconciliation_bootstrap tests.test_http_remediation_transport tests.test_production_remediation
```

The checkout failed before Python started because the execution container could not resolve `github.com` (`Could not resolve host: github.com`). Therefore the Python suite is **not claimed as executed successfully** in this run.

No GitHub Actions workflow was intentionally triggered, rerun, or modified. No Grafana, Loki, Gemini, IAP, Cloud Logging, GCS, Secret Manager, operator, or remediation credential/resource was used.

### Decisions made

1. **Production remediation must be recoverable before it can be enabled.** Missing reconciliation configuration is now a startup error rather than a latent permanent-block condition.
2. **Execution and reconciliation endpoints remain distinct deployment authorities.** The writer command URL and read-only idempotency lookup URL are separately configured even if a deployment chooses to serve both from the same provider.
3. **Endpoint values stay out of incident/browser input.** Only environment-variable names are configurable through the CLI.
4. **Existing reconciliation semantics remain unchanged.** Lookup is GET-only, bodyless, bounded to `accepted` / `not_found` / `unknown`, and never replays remediation.

### Current blockers / unknowns

- The deterministic Python suite remains unexecuted in this environment because the container cannot resolve GitHub for checkout.
- End-to-end `ExecutionSafeIncidentService` coverage with the concrete HTTP reconciliation transport should still prove accepted/not-found/timeout/malformed/repeated reconciliation across an actual uncertainty lifecycle.
- Real-GCS two-instance acceptance, Cloud Run/IAP browser acceptance, real provider idempotency lookup, and real Grafana MCP metric+Loki acceptance still require external credentials/resources.

## Single best next step

**Add end-to-end execution-uncertainty tests using the concrete `HttpRemediationTransport` through `AllowlistedProductionRemediationClient`, proving `accepted`, `not_found`, timeout/error, malformed provider responses, and repeated reconciliation never invoke the remediation execution endpoint a second time and always require fresh Grafana evidence before lifecycle recovery.**

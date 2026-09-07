# StageGuard Progress

## Current status

StageGuard is a personal open-source incident commander for live media workflows. The executable path covers strict telemetry mapping, metric/Loki activation pins, official Grafana MCP evidence, deterministic diagnosis with Loki corroboration, authenticated incident lifecycle orchestration, optional revision-bound Gemini briefing, approval-gated remediation, Grafana recovery verification, bounded durable audit reconstruction, signed GCS incident checkpoints with strict generation CAS, checkpoint observability, fail-closed conflict recovery, remediation execution-uncertainty recovery, Cloud Run/IAP deployment, and operator liveness/readiness/self-observability.

Core invariants:

- Grafana remains the operational evidence plane; infrastructure write credentials remain separate.
- Gemini is advisory only and cannot mutate diagnosis, approval, remediation, or recovery state.
- Human approval is single-use and bound to the exact deterministic evidence revision.
- Fresh investigation clears prior approval/outcome before persisting the new revision.
- Audit history and mutable lifecycle state remain separate persistence concerns.
- Restored checkpoints must match configured telemetry scope and recompute to the persisted evidence revision.
- Production GCS checkpoints require HMAC-SHA-256 authenticity plus strict pinned-generation compare-and-swap.
- Generation conflicts fail closed; the losing process never retries or merges approval-bearing state automatically.
- After a checkpoint conflict, lifecycle work remains blocked until the durable winner is explicitly loaded and fully revalidated.
- A CAS conflict that occurs after a remediation adapter was contacted is treated as execution ambiguity, not merely storage contention.
- Execution ambiguity remains unready after durable-winner reload until provider reconciliation (when required) and a fresh Grafana investigation invalidate the stale approval.
- The API never accepts a caller-supplied remediation operation id for reconciliation; the deterministic id stays server-owned.
- Provider remediation metadata/details, credentials, Gemini output, Grafana secrets, and checkpoint signing material are not persisted.
- Standard Cloud Run production remediation remains disabled by default.
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
- Versioned incident lifecycle checkpoints with owner-only JSON local storage and signed GCS production storage.
- Strict GCS pinned-generation CAS semantics plus isolated two-writer acceptance harness.
- Checkpoint conflict metrics and explicit durable-winner reload/revalidation.
- Fail-closed remediation execution-uncertainty service with provider idempotency reconciliation contract.
- Production bootstrap/API integration for execution uncertainty, including unready state, bounded metric, and authenticated argument-free reconciliation.

## Run log — 2026-09-07 — execution-uncertainty production integration

### Inspected at start

Read `progress.md` completely before deciding what to change. Then inspected:

- repository metadata/default branch;
- `runtime/bootstrap.py`;
- `runtime/api.py`;
- `runtime/execution_safety.py`;
- `runtime/tests/test_execution_safety.py`;
- existing API/bootstrap test structure;
- `EXECUTION_UNCERTAINTY.md`.

The highest-value remaining gap matched the previous handoff: `ExecutionSafeIncidentService` existed, but normal runtime composition still instantiated `IncidentService`; readiness did not recognize `execution_uncertain`; and no authenticated reconciliation endpoint exposed the fail-closed recovery path.

### Exact changes made

Updated `runtime/bootstrap.py`:

- imports and constructs `ExecutionSafeIncidentService` for the normal runtime path;
- leaves the public `RuntimeBundle.service` type compatible with `IncidentService` while using the safer subclass at runtime;
- does not enable production remediation by default or change credential handling.

Updated `runtime/api.py`:

- `/readyz` now returns unready/HTTP 503 when checkpoint state is either `conflicted` or `execution_uncertain`;
- `/metrics` now exports the fixed-label gauge `stageguard_remediation_execution_uncertain 0|1`;
- the gauge contains no incident id, revision, actor, remediation operation id, provider, endpoint, GCS generation, or credential labels;
- added authenticated `POST /v1/execution/reconcile`;
- the reconciliation endpoint accepts an empty JSON object only and rejects caller-supplied operation ids/provider states/targets;
- the endpoint delegates only to the server-owned `reconcile_execution_uncertainty(actor=authenticated_subject)` method;
- bumped the bounded HTTP server version to `StageGuard/0.10`.

Added `runtime/tests/test_execution_safety_api.py`:

- creates a real `ExecutionSafeIncidentService` with a deterministic fake checkpoint race and reconciliation-capable remediation adapter;
- proves a post-provider checkpoint conflict drives `/readyz` to HTTP 503;
- proves the uncertainty metric is set and does not expose the deterministic operation id;
- proves reconciliation before durable-winner reload returns conflict/invalid-state and never calls remediation again;
- proves authenticated checkpoint reload leaves the service `execution_uncertain`;
- proves successful reconciliation performs fresh evidence collection, clears stale approval/outcome, returns to `synchronized`, and keeps the remediation invocation count at exactly one;
- proves the reconciliation endpoint requires authentication and rejects a caller-supplied `operation_id`.

Added `runtime/tests/test_bootstrap_execution_safety.py`:

- verifies normal local runtime composition returns `ExecutionSafeIncidentService` rather than the base service;
- verifies the initial execution-reconciliation state is `clear`.

Updated `EXECUTION_UNCERTAINTY.md`:

- documents the now-integrated production/API state machine;
- documents `/healthz` vs `/readyz` behavior while execution is uncertain;
- documents the bounded uncertainty metric;
- documents the authenticated zero-argument reload/reconciliation sequence and server ownership of the deterministic operation id;
- records the direct lifecycle, HTTP, and bootstrap regression coverage.

### Commits produced this run

- `6620332f` — wire execution-safe lifecycle service into runtime bootstrap
- `b1b64c3e` — expose fail-closed uncertain execution readiness and reconciliation
- `aeb9c29c` — test uncertain execution API safety boundary
- `b155516e` — verify bootstrap composes execution-safe incident service
- `d10ad1ff` — document integrated uncertain execution recovery boundary

### Tests / checks / results

No GitHub Actions workflow was created, triggered, rerun, or modified.

The changed source and test files were written through the authenticated GitHub connector and re-inspected structurally. This automation runtime still does not expose a runnable repository checkout and prior direct checkout attempts fail DNS resolution for `github.com`; therefore the new Python tests are **not claimed as executed successfully** in this run.

No Grafana, Loki, Gemini, IAP, Cloud Logging, GCS, Secret Manager, operator, or remediation credential/resource was used.

### Decisions made

1. **Execution uncertainty is a readiness failure.** Process liveness remains independent, but an instance that cannot prove remediation side-effect state must receive no production traffic that assumes lifecycle consistency.
2. **Reconciliation inputs remain server-owned.** The HTTP caller cannot choose or alter the deterministic provider operation id, provider state, target, evidence revision, or remediation action.
3. **Durable reload remains a separate explicit step.** `/v1/execution/reconcile` does not silently load or merge checkpoint state; operators must first adopt the durable winner through `/v1/checkpoint/reload`.
4. **No action replay during reconciliation.** HTTP regression coverage asserts the remediation provider is contacted exactly once across conflict, reload, and reconciliation.
5. **Observability remains bounded.** Only a 0/1 uncertainty gauge is exported; high-cardinality or sensitive lifecycle/provider identity is excluded.
6. **The safer lifecycle service is now the default composition.** Production safety no longer depends on callers remembering to instantiate a special subclass manually.

### Current blockers / unknowns

- The deterministic Python suite remains unexecuted in this environment because no runnable checkout is exposed and direct `github.com` checkout has failed DNS resolution in prior attempts.
- The default `HttpRemediationTransport` still has no provider-specific reconciliation API. This is deliberate: StageGuard cannot safely invent a provider lookup contract. Production remediation transports must implement `reconcile(...)` before uncertain execution can clear.
- The real-GCS two-instance acceptance harness and Cloud Run/IAP browser acceptance still require external credentials/resources.
- Grafana MCP readiness and full metric+Loki investigation still need acceptance against a real Grafana Cloud or self-hosted instance.
- The operator cockpit does not yet surface a dedicated conflict/uncertainty recovery workflow; the safe API exists, but operators currently need to invoke the endpoints directly.

## Single best next step

**Add a bounded operator-cockpit recovery UX for `conflicted` and `execution_uncertain` states that exposes only safe state, guides the operator through durable checkpoint reload then reconciliation, disables execute/approve controls while blocked, and never accepts or displays the remediation operation id. Add browser-free DOM/asset regression tests ensuring the UI cannot accidentally offer action replay during uncertainty.**

# StageGuard Progress

## Current status

StageGuard is a personal open-source incident commander for live media workflows. The executable path covers strict telemetry mapping, metric/Loki activation pins, official Grafana MCP evidence, deterministic diagnosis with Loki corroboration, authenticated incident lifecycle orchestration, optional revision-bound Gemini briefing, approval-gated remediation, Grafana recovery verification, bounded durable audit reconstruction, signed GCS incident checkpoints with strict generation CAS, checkpoint observability, fail-closed conflict recovery, Cloud Run/IAP deployment, and operator liveness/readiness/self-observability.

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
- New fail-closed remediation execution-uncertainty service and regression tests.

## Run log — 2026-09-07 — remediation execution uncertainty boundary

### Inspected at start

Read `progress.md` completely before deciding what to change. Then inspected:

- repository metadata/default branch;
- `runtime/incident_service.py`;
- `runtime/remediation.py`;
- `runtime/production_remediation.py`;
- `runtime/api.py`;
- `runtime/bootstrap.py`;
- `runtime/tests/test_checkpoint_conflict_recovery.py`.

The highest-value remaining safety gap was confirmed in the existing flow: `execute_approved()` calls `remediate_and_verify()` before recording/persisting the completed lifecycle state. Therefore a GCS checkpoint CAS conflict can occur after the external remediation adapter was already contacted, leaving provider execution ambiguous while the durable winner may still contain an unconsumed approval.

### Exact changes made

Added `runtime/execution_safety.py` with `ExecutionSafeIncidentService`:

- catches `CheckpointConflictError` only at the post-remediation `execute_approved()` boundary, where the adapter has already been contacted;
- records the deterministic `remediation_operation_id` in process memory and enters bounded `execution_uncertain` state;
- blocks ordinary lifecycle mutation and any repeated remediation execution while uncertain;
- requires the existing explicit durable-winner checkpoint reload first;
- keeps execution uncertainty active after reload because durable checkpoint ownership does not prove whether the provider executed the remote side effect;
- supports bounded provider reconciliation states `accepted`, `not_found`, or `unknown`;
- production-style adapters that declare reconciliation required cannot clear uncertainty when provider state is unknown or reconciliation is unavailable;
- after successful provider reconciliation, performs a fresh Grafana investigation as the only allowed lifecycle mutation while uncertain;
- the fresh evidence revision clears the old approval/outcome before another remediation can ever be approved;
- any reconciliation or fresh-investigation failure leaves the process blocked;
- never replays the remediation action and never retries/merges the losing checkpoint write.

Added `runtime/tests/test_execution_safety.py` covering:

- checkpoint conflict after provider contact enters `execution_uncertain`;
- a durable winner containing the old unconsumed approval cannot cause the same approval to execute again;
- durable-winner reload is mandatory before reconciliation;
- reload alone does not clear execution uncertainty;
- production provider reconciliation must resolve to a bounded non-ambiguous state;
- `unknown` provider state remains fail-closed;
- successful reconciliation requires fresh Grafana evidence and clears stale approval/outcome;
- local/simulator remediation can resolve via durable reload + fresh Grafana evidence without an external provider lookup.

Updated `runtime/production_remediation.py`:

- `AllowlistedProductionRemediationClient` now declares `requires_operation_reconciliation = True`;
- adds `reconcile_operation(operation_id)`;
- delegates only to an optional deployment-owned transport `reconcile(...)` capability;
- validates the deterministic `sg-...` operation id first;
- accepts only `accepted` or `not_found`; unsupported capability, errors, or unexpected provider output collapse to `unknown`;
- provider exception text and response detail are not surfaced.

Added `EXECUTION_UNCERTAINTY.md` documenting the safety state machine and provider reconciliation contract.

### Commits produced this run

- `eb45ecc4` — guard uncertain remediation execution after checkpoint conflicts
- `9f1a9cd3` — test fail-closed uncertain remediation reconciliation
- `1160c78a` — add provider idempotency reconciliation contract
- `c105cd1e` — document fail-closed remediation uncertainty model

### Tests / checks / results

No GitHub Actions workflow was created, triggered, or rerun.

Attempted a clean credential-free checkout and targeted test run:

```text
git clone --depth 1 https://github.com/UnknownGod2011/Grafana.git /tmp/stageguard
PYTHONPATH=runtime python -m unittest runtime.tests.test_execution_safety -v
```

The container failed before checkout with:

```text
Could not resolve host: github.com
```

Therefore the new Python suite is **not claimed as executed successfully** in this runtime. The changed files were written through the authenticated GitHub connector. No Grafana, Loki, Gemini, IAP, Cloud Logging, GCS, Secret Manager, operator, or remediation credential/resource was used.

### Decisions made

1. **Post-provider CAS loss is a separate execution safety state.** It cannot be treated as an ordinary storage conflict.
2. **Reload is necessary but insufficient.** Durable state ownership says nothing about whether the remote provider accepted the operation.
3. **No automatic action replay.** The deterministic operation id is for provider reconciliation/idempotency, not permission to retry blindly.
4. **Production reconciliation fails closed.** Missing provider lookup capability and ambiguous/error outcomes remain `unknown`.
5. **Fresh Grafana evidence is mandatory before returning to normal lifecycle operation.** This both re-establishes current system state and invalidates the stale approval.
6. **Provider details stay bounded.** Reconciliation surfaces only coarse state and never raw provider exceptions/responses.

### Current blockers / unknowns

- The deterministic Python suite remains unexecuted in this environment because the container cannot resolve `github.com` for checkout.
- `ExecutionSafeIncidentService` is implemented and tested but is **not yet wired into `runtime/bootstrap.py` or `runtime/api.py`**; production composition still instantiates the base `IncidentService`.
- The API readiness logic currently understands `conflicted` but not `execution_uncertain`.
- No authenticated argument-free execution-reconciliation endpoint is exposed yet.
- The default `HttpRemediationTransport` does not implement a provider-specific reconciliation API because StageGuard cannot safely invent a production provider endpoint contract; custom transports can implement it now.
- The real-GCS two-instance acceptance harness and Cloud Run/IAP browser acceptance still need execution with external credentials/resources.
- Grafana MCP readiness and full metric+Loki investigation still need acceptance against a real Grafana Cloud or self-hosted instance.

## Single best next step

**Wire `ExecutionSafeIncidentService` into `runtime/bootstrap.py` and `runtime/api.py`: make `execution_uncertain` force `/readyz` to 503, export a fixed-label uncertainty gauge, and add an authenticated argument-free reconciliation endpoint that invokes only `reconcile_execution_uncertainty()` after durable-winner reload. Add API/bootstrap tests proving an old unconsumed durable approval can never be replayed after an uncertain provider contact.**

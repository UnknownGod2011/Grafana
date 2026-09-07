# Remediation execution uncertainty

StageGuard treats a checkpoint compare-and-swap conflict **after** a remediation adapter was contacted as a distinct safety condition. The losing process must not infer whether the provider executed the action from its failed checkpoint write, and it must never replay the same approval automatically.

StageGuard also treats a **restored production checkpoint with an approval but no outcome** as execution-ambiguous. A checkpoint cannot prove whether the previous process crashed before or after contacting the provider. For production adapters that require reconciliation, restart therefore fails closed instead of making the restored approval executable again.

## State machine

`ExecutionSafeIncidentService` adds an `execution_uncertain` state on top of the existing checkpoint-conflict boundary.

1. An operator approves one deterministic evidence revision.
2. `execute_approved()` contacts the remediation adapter using StageGuard's deterministic `sg-...` operation id.
3. If the remediation/recovery result cannot be checkpointed because another writer won CAS, the service enters `execution_uncertain`.
4. All ordinary lifecycle mutation is blocked. Reissuing `/v1/execute` or calling the adapter again is forbidden.
5. The durable checkpoint winner must be explicitly reloaded and fully validated through authenticated `POST /v1/checkpoint/reload`.
6. Reloading resolves checkpoint ownership only; it does **not** clear `execution_uncertain`.
7. Production adapters must reconcile the deterministic provider operation id. Only bounded states `accepted` or `not_found` are considered resolved; errors, unsupported reconciliation, unexpected provider output, and ambiguous transport outcomes collapse to `unknown` and remain blocked.
8. An authenticated operator invokes argument-free `POST /v1/execution/reconcile`. The operation id is retained server-side and cannot be supplied or substituted by the caller.
9. StageGuard then performs a fresh Grafana investigation. The fresh evidence revision clears the stale approval/outcome before another remediation can ever be approved.

The implementation intentionally does not merge the losing in-memory outcome into the durable winner and does not retry the failed checkpoint save.

## Restart safety

A process can terminate at any instruction boundary after a production approval has been persisted. If the durable checkpoint contains `approval != null` and `outcome == null`, StageGuard cannot distinguish these cases from checkpoint state alone:

- the action was never sent;
- the action was sent but the process crashed before receiving the response;
- the provider accepted the action but the process crashed before persisting the outcome;
- a CAS conflict occurred after provider contact and before the in-memory uncertainty flag could be observed again.

For remediation adapters declaring `requires_operation_reconciliation = True`, a newly constructed `ExecutionSafeIncidentService` therefore derives the deterministic operation id from the restored report + approval and immediately enters `execution_uncertain` with reconciliation phase `reloaded`. The restored checkpoint has already been loaded and validated during construction, so an additional checkpoint reload is not required before provider reconciliation.

This policy is deliberately conservative: a genuinely unused production approval may be invalidated after restart. That cost is preferable to silently replaying a potentially completed external side effect. Successful `accepted` or `not_found` reconciliation still requires fresh Grafana evidence, clears the old approval, and forces a new human approval before any later remediation can execute.

Local/simulator adapters that do not require provider reconciliation keep their existing restart behavior.

## Runtime health and observability

Production bootstrap constructs `ExecutionSafeIncidentService` by default. While `checkpoint_state()` is `execution_uncertain`:

- `/healthz` remains HTTP 200 because the process is alive;
- `/readyz` is HTTP 503 even when Grafana evidence-plane checks are healthy;
- `/v1/incident` exposes only the bounded checkpoint state, not the provider operation id;
- `/metrics` exports `stageguard_remediation_execution_uncertain 1` with no incident, actor, operation-id, provider, endpoint, generation, or credential labels;
- normal investigation, briefing, approval, and execution mutations remain blocked.

The reconciliation endpoint is authenticated and accepts an empty JSON object only. Caller-supplied operation ids, provider states, remediation targets, or evidence are rejected.

## Production adapter contract

`AllowlistedProductionRemediationClient` declares `requires_operation_reconciliation = True`. A deployment-specific remediation transport may implement:

```python
def reconcile(operation_id: str, *, timeout_seconds: float) -> str:
    ...
```

It must return only one of:

- `accepted` — the provider's idempotency record proves the operation was accepted;
- `not_found` — the provider proves there is no matching operation record;
- `unknown` — anything ambiguous or unverifiable.

If a transport does not implement reconciliation, the production adapter returns `unknown`; StageGuard remains blocked. Provider response bodies, credentials, endpoint details, and exception strings are not surfaced through the reconciliation result.

The concrete `HttpRemediationTransport` uses a separate GET-only reconciliation endpoint. Its lookup sends no remediation command body, target, production id, or action; malformed responses, timeouts, unexpected status codes, provider errors, oversized bodies, wrong operation-id echoes, and unknown states all collapse to `unknown`.

## Local development

Local/simulator adapters do not declare provider reconciliation as mandatory. They still require durable-winner reload and a fresh Grafana investigation after an in-process uncertain execution, but no external idempotency lookup is required. A normal local restart with a pending approval does not automatically enter the production restart-safety state.

## Regression coverage

`runtime/tests/test_execution_safety.py` exercises the lifecycle state machine directly, including restart of a persisted pending production approval and preservation of local-adapter restart semantics.

`runtime/tests/test_execution_safety_http_transport.py` exercises the concrete HTTPS writer + read-only reconciliation transport through `AllowlistedProductionRemediationClient` and proves that:

- accepted reconciliation collects fresh evidence and never sends a second remediation POST;
- provider 404 maps only to bounded `not_found` and still never replays execution;
- timeout and malformed responses remain fail-closed;
- reconciliation GET requests are bodyless;
- repeated reconciliation after success performs no provider network call and no remediation replay.

`runtime/tests/test_execution_safety_api.py` exercises the HTTP safety boundary and proves that:

- execution uncertainty forces readiness to fail closed;
- the uncertainty metric contains no deterministic operation id;
- reconciliation cannot run before durable-winner reload for an in-process CAS conflict;
- the endpoint is authenticated and argument-free;
- reload keeps execution uncertainty active;
- successful reconciliation collects fresh evidence and clears the stale approval/outcome;
- the remediation adapter is contacted exactly once throughout the conflict/reload/reconciliation path.

`runtime/tests/test_bootstrap_execution_safety.py` verifies that normal runtime composition uses `ExecutionSafeIncidentService` rather than the base lifecycle service.

# Remediation execution uncertainty

StageGuard treats a checkpoint compare-and-swap conflict **after** a remediation adapter was contacted as a distinct safety condition. The losing process must not infer whether the provider executed the action from its failed checkpoint write, and it must never replay the same approval automatically.

Checkpoint schema v2 adds a durable, authenticated execution phase so restart safety can distinguish an approval that is definitely unused from an operation that may have been dispatched. The checkpoint contains only the bounded phase; provider response bodies, credentials, endpoint details, and operation state remain outside durable lifecycle state.

## Checkpoint v2 execution phases

The persisted phase is one of:

- `none` — no approval is currently actionable;
- `approved` — an approval exists and StageGuard has **not** crossed the provider-dispatch barrier;
- `dispatching` — StageGuard durably recorded that provider contact may occur, so restart must assume the external side effect may have happened;
- `resolved` — an approval and bounded remediation outcome are durably recorded.

For reconciliation-required production adapters, `ExecutionSafeIncidentService.execute_approved()` persists `dispatching` **before** invoking the remediation adapter. If that pre-dispatch checkpoint write loses compare-and-swap, the provider is not contacted and the failure remains an ordinary checkpoint conflict. Once `dispatching` is durable, provider errors, process termination, recovery-verification failures, or a later checkpoint conflict are treated as execution ambiguity and never trigger automatic replay.

The ordinary lifecycle checkpoint writer derives `none`, `approved`, and `resolved` from approval/outcome state. Only the execution-safety layer writes the explicit `dispatching` barrier.

## Backward-compatible v1 restore

Schema v1 remains readable. Because v1 contains no execution phase, a restored v1 checkpoint with `approval != null` and `outcome == null` is mapped internally to `legacy_unknown`. For production adapters requiring reconciliation, `legacy_unknown` remains fail-closed exactly like the previous conservative restart policy.

A v2 `approved` checkpoint is different: it proves the dispatch barrier was never crossed, so a production process may safely restart and execute that still-valid approval without provider reconciliation. This removes the previous false-positive invalidation of genuinely unused approvals while preserving replay safety.

## State machine

`ExecutionSafeIncidentService` adds an `execution_uncertain` state on top of the existing checkpoint-conflict boundary.

1. An operator approves one deterministic evidence revision. The durable v2 phase is `approved`.
2. Before any production provider call, StageGuard persists phase `dispatching` with the same evidence revision and approval.
3. Only after that durable barrier succeeds does `execute_approved()` contact the remediation adapter using StageGuard's deterministic `sg-...` operation id.
4. Successful execution + recovery verification persists a bounded outcome; the durable phase becomes `resolved`.
5. If provider execution/verification becomes ambiguous after `dispatching`, or the post-provider checkpoint loses CAS, the service enters `execution_uncertain`.
6. All ordinary lifecycle mutation is blocked. Reissuing `/v1/execute` or calling the adapter again is forbidden.
7. For a post-provider CAS conflict, the durable checkpoint winner must be explicitly reloaded and fully validated through authenticated `POST /v1/checkpoint/reload`.
8. Production adapters reconcile the deterministic provider operation id. Only bounded states `accepted` or `not_found` are considered resolved; errors, unsupported reconciliation, unexpected provider output, and ambiguous transport outcomes collapse to `unknown` and remain blocked.
9. An authenticated operator invokes argument-free `POST /v1/execution/reconcile`. The operation id is retained server-side and cannot be supplied or substituted by the caller.
10. StageGuard then performs a fresh Grafana investigation. The fresh evidence revision clears stale approval/outcome before another remediation can ever be approved.

The implementation intentionally does not merge a losing in-memory outcome into the durable winner and does not retry a failed checkpoint save.

## Restart safety

Checkpoint v2 makes restart behavior precise:

- `approved`: provider dispatch has not begun; the still-valid approval can resume after restart;
- `dispatching`: provider contact may have happened; restart enters `execution_uncertain` with reconciliation phase `reloaded`;
- `resolved`: the approval is consumed and cannot execute again;
- v1 `legacy_unknown`: treated as execution-ambiguous because historical state cannot prove whether provider dispatch occurred.

For `dispatching` and `legacy_unknown`, a newly constructed `ExecutionSafeIncidentService` derives the deterministic operation id from the restored report + approval and immediately enters `execution_uncertain`. Construction has already loaded and validated the durable checkpoint, so a separate reload is not required before reconciliation in this restart path.

Successful `accepted` or `not_found` reconciliation still requires fresh Grafana evidence, clears the old approval, and forces a new human approval before any later remediation can execute.

Local/simulator adapters that do not require provider reconciliation keep their existing restart behavior.

## Integrity and authenticity

The execution phase is inside the canonical checkpoint state covered by SHA-256 integrity and, for production GCS checkpoints, HMAC-SHA-256 authenticity. A storage writer without the signing key cannot change `approved` to `dispatching` or vice versa while retaining a valid production checkpoint signature.

The phase is intentionally low-cardinality and provider-neutral. StageGuard does not persist provider response bodies, provider status payloads, credentials, remediation endpoints, deterministic operation ids, or infrastructure metadata in the checkpoint.

## Runtime health and observability

Production bootstrap constructs `ExecutionSafeIncidentService` by default. While `checkpoint_state()` is `execution_uncertain`:

- `/healthz` remains HTTP 200 because the process is alive;
- `/readyz` is HTTP 503 even when Grafana evidence-plane checks are healthy;
- `/v1/incident` exposes only the bounded checkpoint/reconciliation state, not the provider operation id;
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

`runtime/tests/test_incident_checkpoint.py` covers v2 serialization, phase derivation, v1 pending-approval migration to `legacy_unknown`, provider-detail exclusion, and signed phase-tamper rejection.

`runtime/tests/test_execution_phase_v2.py` proves that:

- `dispatching` is saved before a production remediation adapter is contacted;
- a v2 `approved` production checkpoint remains safely executable after restart;
- a restored `dispatching` checkpoint requires reconciliation and cannot replay remediation;
- a restored v1 pending approval remains fail-closed.

`runtime/tests/test_execution_safety.py` continues to exercise conflict/reload/reconciliation behavior and custom stores without phase support.

`runtime/tests/test_execution_safety_http_transport.py` exercises the concrete HTTPS writer + read-only reconciliation transport through `AllowlistedProductionRemediationClient` and proves accepted/not-found/timeout/malformed/repeated reconciliation paths never send a second remediation POST.

`runtime/tests/test_execution_safety_api.py` exercises the authenticated HTTP safety boundary, readiness behavior, bounded reconciliation state, and reload/reconcile workflow.

`runtime/tests/test_bootstrap_execution_safety.py` verifies that normal runtime composition uses `ExecutionSafeIncidentService` rather than the base lifecycle service.

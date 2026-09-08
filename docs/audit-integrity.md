# Audit-integrity deployment policy

StageGuard separates the observed audit-integrity state from the configured readiness policy. This is deliberate: operators must be able to distinguish a legacy/unbound checkpoint from an actual integrity failure without weakening production readiness.

## Policies

- `allow_unbound_legacy`: intended for local development and controlled migration. `unbound_legacy` can remain ready when the rest of the evidence plane is healthy, but `failed` never can.
- `require_verified`: hardened mode. Readiness requires `audit_integrity=verified`; `disabled`, `unbound_legacy`, and `failed` all keep `/readyz` false.

The Cloud Run composition automatically selects `require_verified` when durable GCS checkpointing is enabled alongside the durable audit backend. Deployments without durable checkpointing stay in the migration-compatible mode rather than claiming a proof they cannot produce.

## Legacy checkpoint migration

Do not edit a legacy checkpoint to add a digest, copy a hash from another environment, or temporarily relax the production policy merely to make readiness green. A valid schema-v3 checkpoint must be produced by StageGuard from the actual durable audit lineage. After a legitimate lifecycle/audit write establishes that binding, restart the service and confirm `/v1/incident` reports `audit_integrity=verified` and `/readyz` becomes ready.

The operator cockpit displays both the bounded state and policy. Under `require_verified`, a legacy/unbound checkpoint is shown as an explicit lifecycle safety block; approval, execution, investigation, and briefing controls remain disabled until authenticated state is established.

## Operational checks

Use `/readyz` for readiness and `/metrics` for low-cardinality alerting. The relevant metrics are `stageguard_audit_integrity{state=...}`, `stageguard_audit_integrity_policy{policy=...}`, and `stageguard_audit_integrity_policy_satisfied`. Do not alert on checkpoint digests, incident IDs, provider operation IDs, endpoints, actors, or other unbounded values.

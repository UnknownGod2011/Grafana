# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the runtime evidence and observability plane. The current executable path includes configurable telemetry mapping, Prometheus/Loki/Grafana MCP evidence, deterministic diagnosis, revision-bound Gemini briefing, authenticated approval-gated remediation, Grafana recovery verification, signed checkpoint persistence with optimistic concurrency, provider idempotency reconciliation, Cloud Run/IAP deployment, operator readiness/metrics, a same-origin recovery cockpit, checkpoint schema v2 execution phases, bounded reconciliation reasons, append-only reconciliation audit events, deterministic tamper-evident audit chaining, checkpoint schema v3 audit-chain binding, restore-time orphan-tail rejection, and explicit audit-integrity observability.

Core safety invariants:

- Grafana is the evidence plane; infrastructure write credentials remain isolated from Grafana/MCP access.
- Gemini is advisory and cannot mutate approval, remediation, or recovery state.
- Human approval is single-use and bound to an exact evidence revision.
- Production remediation uses a deterministic idempotency identity and never automatically replays ambiguous external side effects.
- Phase-capable stores persist `dispatching` before provider contact; restored `dispatching` and legacy ambiguous approvals require provider reconciliation plus fresh Grafana evidence.
- GCS checkpoints are HMAC-authenticated and use generation compare-and-swap.
- `/readyz` fails closed for checkpoint conflict, execution uncertainty, failed audit integrity, or a configured audit-integrity policy violation.
- Concrete remediation reconciliation is GET-only and cannot carry a remediation body.
- Reconciliation audit entries contain only bounded result/reason dimensions; provider payloads, operation IDs, endpoints, credentials, generations, and raw exceptions are excluded.
- Audit-chain state uses domain-separated SHA-256, strict contiguous sequence numbers, and never advances its trusted head when the underlying audit append fails.
- Schema v3 is emitted only when a real durable-audit chain head is available; non-durable/in-memory callers remain on v2 rather than receiving a fake integrity proof.
- The authenticated checkpoint audit sequence is authoritative on restore. Durable audit events beyond that head are treated as uncommitted/orphan lineage and are never silently adopted.
- Audit-integrity and policy telemetry are fixed-cardinality; invalid state/policy values collapse to fail-closed bounded values rather than becoming metric labels.

## Completed milestones

- Deterministic media telemetry simulator plus local Prometheus/Grafana stack.
- Official Grafana MCP integration with bounded Prometheus/Loki evidence tools.
- Configurable telemetry mappings, activation preflight, and strict evidence scope.
- Approval-gated remediation and telemetry-only recovery proof.
- Credential-isolated HTTPS remediation transport with deterministic idempotency identity.
- Provider-neutral GET-only reconciliation with bounded `accepted` / `not_found` / `unknown` states.
- Revision-bound Gemini incident-commander briefing layer.
- Verified Google IAP identity, Cloud Logging audit integration, and Cloud Run deployment path.
- Durable checkpoint recovery, strict CAS conflict handling, and operator recovery cockpit.
- Checkpoint schema v2 phases plus real crash/SIGKILL and HTTPS ambiguity coverage.
- Fixed-cardinality reconciliation reasons in operator state, readiness, metrics, cockpit guidance, and conflict/crash matrices.
- Append-only bounded reconciliation audit events and concrete TLS/SIGKILL audit ordering acceptance.
- Credential-free tamper-evident audit-chain primitive and checkpoint schema v3 authenticated chain binding.
- Runtime chain-head persistence across ordinary, dispatching, and reconciliation checkpoints.
- Restore-time durable audit verification including mutation/deletion/reordering and orphan-tail rejection.
- Fixed-cardinality `audit_integrity={disabled,unbound_legacy,verified,failed}` exposure through `/v1/incident`, `/readyz`, and Prometheus metrics.
- Explicit audit-integrity readiness policy with migration and hardened production modes.

## Run log — 2026-09-09 — production audit-integrity policy

### Inspected at start

Read `progress.md` completely before choosing work. Inspected the current `main` head, `runtime/api.py`, `runtime/bootstrap.py`, `runtime/cloudrun_entrypoint.py`, `runtime/tests/test_audit_integrity_observability.py`, and `runtime/tests/test_cloudrun_entrypoint.py`. Confirmed the previous run exposed `audit_integrity` but intentionally allowed `unbound_legacy` readiness with no production policy control.

### Exact changes made

1. Added an explicit bounded audit-integrity policy to `runtime/api.py`.
   - Policies are only `allow_unbound_legacy` and `require_verified`.
   - Added bounded policy lookup with invalid runtime values collapsing to `require_verified`.
   - `/v1/incident` now exposes `audit_integrity_policy` alongside the underlying integrity state.
   - `/readyz` now exposes the policy and fails readiness when `require_verified` is configured and the integrity state is anything other than `verified`.
   - Existing `failed` integrity remains fail-closed under both policies.
   - Added fixed-cardinality `stageguard_audit_integrity_policy{policy=...}` one-hot metrics and `stageguard_audit_integrity_policy_satisfied`.
   - No checkpoint digest, audit sequence, incident ID, operation ID, endpoint, provider state, actor, or exception text is accepted as a metric label.

2. Wired policy configuration through `runtime/bootstrap.py`.
   - Added `audit_integrity_policy` to `build_runtime()` with local/backward-compatible default `allow_unbound_legacy`.
   - Added strict normalization/validation before runtime construction.
   - Added CLI `--audit-integrity-policy {allow_unbound_legacy,require_verified}`.
   - Runtime services carry the normalized policy as bounded configuration before the HTTP server is created.

3. Hardened the immutable Cloud Run composition in `runtime/cloudrun_entrypoint.py`.
   - Cloud Run with GCS durable checkpointing now automatically passes `--audit-integrity-policy require_verified` because Cloud Logging already supplies a durable audit reader in that composition.
   - Cloud Run without durable checkpointing explicitly uses `allow_unbound_legacy`; it does not pretend an authenticated v3 checkpoint head exists on ephemeral storage.
   - Production remediation remains disabled by the Cloud Run entrypoint.

4. Added `runtime/tests/test_audit_integrity_policy.py`.
   - Proves hardened mode blocks `disabled`, `unbound_legacy`, and `failed`, while permitting only `verified` when the evidence plane is otherwise healthy.
   - Proves migration mode still permits `unbound_legacy` but never permits `failed`.
   - Proves invalid runtime policy values fail hardened and cannot leak into metric labels.
   - Proves the bootstrap CLI exposes only the two bounded modes.
   - Proves Cloud Run + GCS selects `require_verified` and Cloud Run without durable checkpointing selects the migration-compatible mode.

### Tests / checks / results

- Repository inspection and Git object writes succeeded through the GitHub connector.
- Attempted a fresh local clone before test execution; cloning failed before Python started because the execution container still cannot resolve `github.com` (`Could not resolve host: github.com`).
- Therefore the new targeted tests are **not claimed green locally** in this run.
- No GitHub Actions workflow was manually triggered or rerun.
- No production Grafana, Gemini, GCS, IAP, Cloud Logging, Secret Manager, operator, or remediation credentials/resources were touched.

### Decisions made

1. **Separate state from policy.** `unbound_legacy` remains visible as the actual integrity condition instead of being rewritten to `failed`; the policy independently determines readiness.
2. **Fail invalid policy values hardened.** A configuration bug must not silently preserve readiness or create arbitrary metric cardinality.
3. **Keep local development backward compatible.** The bootstrap default remains `allow_unbound_legacy`, so existing local/demo flows do not require durable authenticated audit state.
4. **Harden the durable Cloud Run path automatically.** When the production entrypoint has GCS checkpoints plus its fixed Cloud Logging audit backend, only a verified v3 audit/checkpoint binding can satisfy readiness.
5. **Do not require verification when no durable checkpoint exists.** A Cloud Run deployment without GCS remains explicitly non-durable rather than entering a permanently impossible `require_verified` state.

### Current blockers / unknowns

- The new policy tests still need execution in a complete checkout before a green result can be claimed.
- Multi-instance append-before-CAS can still leave orphan/duplicate events in Cloud Logging. Restore rejects them safely, but a production lineage/commit-marker strategy remains desirable.
- Real GCS generation behavior still needs live/emulated provider-backed acceptance beyond the credential-free generation-aware fake.
- Real Cloud Run/IAP browser acceptance, live Grafana MCP acceptance, real GCS acceptance, and a real remediation provider remain external-resource validation tasks.

## Single best next step

**Extend the same-origin operator cockpit and deployment documentation to surface the configured audit-integrity policy and explain why `require_verified` is blocking readiness, then add an end-to-end restart test that starts from a legacy v2 checkpoint under hardened mode, proves readiness remains false, performs a legitimate lifecycle/audit write that emits authenticated v3 state, restarts, and proves readiness becomes true only after the verified binding is restored.**

## Previous run summary

The previous run exposed `audit_integrity={disabled,unbound_legacy,verified,failed}` through incident state, readiness, and fixed-cardinality metrics, with `failed` independently forcing readiness false.

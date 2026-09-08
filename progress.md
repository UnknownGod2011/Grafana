# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the runtime evidence and observability plane. The executable path includes configurable telemetry mapping, Prometheus/Loki/Grafana MCP evidence, deterministic diagnosis, revision-bound Gemini briefing, authenticated approval-gated remediation, Grafana recovery verification, signed checkpoint persistence with optimistic concurrency, provider idempotency reconciliation, Cloud Run/IAP deployment, operator readiness/metrics, a same-origin recovery cockpit, checkpoint schema v2 execution phases, bounded reconciliation reasons, append-only reconciliation audit events, deterministic tamper-evident audit chaining, checkpoint schema v3 audit-chain binding, restore-time orphan-tail rejection, explicit audit-integrity observability, and hardened audit-integrity readiness policy.

Core safety invariants:

- Grafana is the evidence plane; infrastructure write credentials remain isolated from Grafana/MCP access.
- Gemini is advisory and cannot mutate approval, remediation, or recovery state.
- Human approval is single-use and bound to an exact evidence revision.
- Production remediation uses deterministic idempotency identity and never automatically replays ambiguous external side effects.
- Phase-capable stores persist `dispatching` before provider contact; restored ambiguity requires reconciliation plus fresh Grafana evidence.
- GCS checkpoints are HMAC-authenticated and use generation compare-and-swap.
- `/readyz` fails closed for checkpoint conflict, execution uncertainty, failed audit integrity, or configured audit-integrity policy violation.
- Reconciliation is GET-only and cannot carry a remediation body.
- Reconciliation audit entries contain only bounded result/reason dimensions.
- Audit-chain state uses domain-separated SHA-256 and strict contiguous sequence numbers.
- Schema v3 is emitted only when a real durable-audit chain head is available.
- The authenticated checkpoint audit sequence is authoritative on restore; orphan durable audit tails are rejected.
- Audit-integrity state/policy telemetry is fixed-cardinality; invalid values collapse fail-closed.

## Completed milestones

- Deterministic media telemetry simulator plus local Prometheus/Grafana stack.
- Official Grafana MCP integration with bounded Prometheus/Loki evidence tools.
- Configurable telemetry mappings, activation preflight, and strict evidence scope.
- Approval-gated remediation and telemetry-only recovery proof.
- Credential-isolated HTTPS remediation transport with deterministic idempotency identity.
- Provider-neutral GET-only reconciliation with bounded outcomes.
- Revision-bound Gemini incident-commander briefing layer.
- Google IAP identity, Cloud Logging audit integration, and Cloud Run deployment path.
- Durable checkpoint recovery, CAS conflict handling, operator recovery cockpit, execution phases, crash/SIGKILL ambiguity coverage, reconciliation reason model, bounded reconciliation audit events, tamper-evident audit chain, schema-v3 binding, restore-time audit verification, and integrity observability/policy.
- Same-origin cockpit now surfaces audit-integrity state/policy and treats hardened policy violations as independent fail-closed lifecycle blocks.

## Run log — 2026-09-09 — operator audit-integrity policy safety

### Inspected at start

Read `progress.md` completely before choosing work. Inspected current `main`, `runtime/api.py`, `runtime/operator_console.py`, `runtime/tests/test_operator_console.py`, and `runtime/tests/test_runtime_audit_checkpoint_binding.py`. Confirmed the previous run enforced `require_verified` in readiness, but the browser cockpit still only modeled checkpoint conflict/execution uncertainty and therefore could not explain a hardened audit-integrity block to operators.

### Exact changes made

1. Extended `runtime/operator_console.py` with a dedicated audit-integrity safety card.
   - Consumes only bounded `audit_integrity` values: `disabled`, `unbound_legacy`, `verified`, `failed`.
   - Consumes only bounded policies: `allow_unbound_legacy`, `require_verified`.
   - Invalid integrity values collapse to `failed`; invalid policies collapse to `require_verified`.
   - `audit_integrity=failed` blocks lifecycle controls under every policy.
   - `require_verified` blocks lifecycle controls unless integrity is exactly `verified`.
   - The block is independent from checkpoint conflict/execution uncertainty and is reflected in the connection safety indicator.
   - Hardened legacy guidance explicitly says a legitimate lifecycle/audit write must establish authenticated v3 state and warns against bypassing the policy or editing checkpoint files manually.
   - Existing uncertain-execution recovery remains replay-safe and continues to require fresh Grafana evidence.

2. Added `runtime/tests/test_operator_integrity_policy.py`.
   - Asserts the bounded state/policy allowlists are present in the browser contract.
   - Asserts hardened audit policy participates in the lifecycle safety block and disables investigation/approval/execution.
   - Asserts migration guidance does not suggest bypassing integrity controls.
   - Asserts provider operation IDs, provider URLs, and browser persistence remain absent.
   - Asserts invalid server values collapse to the hardened fail-closed states.

3. Added `docs/audit-integrity.md`.
   - Documents migration versus hardened policy semantics.
   - Documents the Cloud Run durable-path behavior.
   - Gives a safe legacy checkpoint migration procedure and explicitly prohibits manual digest/checkpoint fabrication or temporary policy relaxation merely to force readiness green.
   - Documents fixed-cardinality readiness/metrics checks for operators.

### Tests / checks / results

- Repository reads and Git object writes succeeded through the GitHub connector.
- The local execution container still cannot resolve `github.com`, so a complete checkout and Python test run could not be started; the new tests are therefore **not claimed green locally**.
- No GitHub Actions workflow was manually triggered or rerun.
- No production Grafana, Gemini, GCS, IAP, Cloud Logging, Secret Manager, operator, or remediation credentials/resources were touched.

### Decisions made

1. **Audit policy is a lifecycle safety gate, not cosmetic status.** The cockpit disables mutating and investigative lifecycle controls when hardened integrity is unsatisfied so browser behavior matches `/readyz`.
2. **State and policy remain separate.** Operators can distinguish `unbound_legacy` migration state from true `failed` integrity without weakening hardened readiness.
3. **Unknown browser inputs fail hardened.** Future server/UI version skew cannot silently enable controls or create arbitrary policy states.
4. **No manual migration shortcuts.** A legacy checkpoint becomes trusted only through StageGuard producing a real schema-v3 binding from the durable audit lineage.

### Current blockers / unknowns

- The new cockpit regressions still need execution in a complete checkout before a green result can be claimed.
- The full end-to-end legacy-v2 -> hardened-unready -> legitimate v3 binding -> restart -> verified-ready migration test remains to be implemented; constructing it safely requires reusing the repository's checkpoint helpers rather than hand-authoring an invalid legacy document.
- Multi-instance append-before-CAS can still leave orphan/duplicate events in Cloud Logging; restore rejects them safely, but a production lineage/commit-marker strategy remains desirable.
- Real GCS generation behavior, Cloud Run/IAP browser acceptance, live Grafana MCP acceptance, and a real remediation provider remain external-resource validation tasks.

## Single best next step

**Implement the credential-free end-to-end migration acceptance test using the real checkpoint serializers/stores: create a legitimate schema-v2 legacy checkpoint, start under `require_verified` and prove `/readyz` is false with `unbound_legacy`, perform the minimum legitimate lifecycle/audit transition that emits authenticated schema-v3 state without bypassing policy semantics, restart from the same durable audit/checkpoint pair, and prove `audit_integrity=verified`, readiness true, sequence continuity, and no stale approval/remediation replay.**

## Previous run summary

The previous run added the bounded `allow_unbound_legacy` / `require_verified` production policy, fixed-cardinality policy telemetry, bootstrap configuration, and automatic hardened Cloud Run selection when GCS durable checkpointing is configured.

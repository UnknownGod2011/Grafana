# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the runtime evidence and observability plane. The executable path includes configurable Prometheus/Loki/Grafana MCP evidence, deterministic diagnosis, revision-bound Gemini briefing, authenticated approval-gated remediation, Grafana recovery verification, durable checkpointing with optimistic concurrency, provider reconciliation, Cloud Run/IAP deployment, operator readiness/metrics, a same-origin recovery cockpit, execution-safe dispatch barriers, tamper-evident audit chaining, checkpoint schema v3 audit-chain binding, hardened audit-integrity readiness policy, authenticated winning-lineage selection for multi-writer append-before-CAS audit streams, schema-v4 authenticated audit-anchor checkpoints, an anchor-aware incident-service/runtime layer for bounded-suffix restore, and an explicit composition that combines anchor-aware restore with execution-safe remediation semantics.

Core safety invariants:

- Grafana is the evidence plane; infrastructure write credentials stay isolated from Grafana/MCP access.
- Gemini is advisory and cannot mutate approval, remediation, or recovery state.
- Human approval is single-use and bound to the exact evidence revision.
- Production remediation uses deterministic idempotency identity and does not automatically replay ambiguous external side effects.
- `dispatching` is durably persisted before provider contact when the checkpoint store supports execution phases.
- Reconciliation is GET-only and ambiguous provider state requires fresh Grafana evidence before recovery completion.
- GCS checkpoints are HMAC-authenticated and generation-CAS protected.
- Audit chain state is domain-separated SHA-256 with contiguous sequence numbers.
- The authenticated checkpoint chain head is lifecycle authority; losing-writer audit residue cannot manufacture approval, outcome, recovery, or operator timeline state.
- Audit anchors are authenticated compaction boundaries, not new trust roots, and must satisfy `anchor <= chain <= lifecycle`.
- Anchor promotion becomes in-memory authority only after checkpoint persistence succeeds; a CAS-losing writer cannot promote its proposed anchor.
- Branched lineage selection and durable candidate reads are explicitly bounded and fail closed on candidate/state explosion or silent truncation.
- `/readyz` fails closed for checkpoint conflict, execution uncertainty, audit-integrity failure, or configured integrity-policy violation.

## Completed milestones

- Deterministic media telemetry simulator and local Prometheus/Grafana stack.
- Official Grafana MCP integration with bounded Prometheus/Loki evidence tools.
- Configurable telemetry mappings, activation preflight, and evidence-scope validation.
- Approval-gated remediation and telemetry-only recovery proof.
- Credential-isolated HTTPS remediation transport with deterministic idempotency identity.
- Provider-neutral GET-only reconciliation with bounded outcomes/reasons.
- Revision-bound Gemini incident commander briefing layer.
- Google IAP identity, Cloud Logging audit integration, and Cloud Run deployment path.
- Durable checkpoint recovery, CAS conflict handling, operator cockpit, crash/SIGKILL ambiguity coverage, tamper-evident audit chain, schema-v3 binding, integrity observability/policy, legacy-v2 to verified-v3 migration acceptance, and authenticated winning-lineage runtime restore.
- Authenticated audit-anchor primitive, Cloud Logging post-anchor candidate-range reads, schema-v4 anchor persistence contract, executable anchor-aware JSONL/runtime service layer, and cooperative execution-safe + anchor-aware service composition.

## Run log — 2026-09-09 — anchor + execution-safety composition

### Inspected at start

Read `progress.md` completely before choosing work. Inspected current `main`, `runtime/anchored_incident_service.py`, `runtime/execution_safety.py`, `runtime/bootstrap.py`, `runtime/incident_service.py`, the anchored runtime tests, and the bootstrap execution-safety regression. Confirmed the next safe integration seam: the anchor-aware subclass and execution-safe subclass both use cooperative `super()` over `IncidentService`, so they can be composed without duplicating base initialization or weakening either layer.

### Exact changes made

1. Added `runtime/anchored_execution_safety.py`.
   - Added `AnchoredExecutionSafeIncidentService(AnchoredIncidentService, ExecutionSafeIncidentService)`.
   - The intentional MRO is `AnchoredIncidentService -> ExecutionSafeIncidentService -> IncidentService`, preserving anchor initialization/persistence plus execution uncertainty, dispatch barriers, and reconciliation behavior while reaching base initialization exactly once.
   - No production/bootstrap default was switched in this increment; the composition is isolated and reversible until regression execution can be completed.
2. Added `runtime/tests/test_anchored_execution_safety.py`.
   - Verifies the service satisfies both parent runtime contracts.
   - Verifies schema-v4 emission and verified restart after physical pre-anchor JSONL compaction while execution reconciliation remains clear.
   - Verifies checkpoint CAS conflict leaves the proposed anchor unauthenticated and preserves the execution-safety conflict state.
3. Preserved CI/resource safety.
   - Changes are prepared as one Git tree/commit/ref update rather than repeated per-file pushes.
   - No workflow rerun, production credential use, or external remediation/Grafana/GCP mutation is part of this increment.

### Tests / checks / results

- Repository inspection and Git object creation succeeded through the connected GitHub integration.
- The execution environment still does not provide a complete local checkout/import path for running the repository test suite, so no green pytest/unittest result is claimed for the new composition yet.
- The composition is deliberately small and relies on cooperative `super()` already present in both parent classes; runtime tests were added specifically to catch MRO/initialization regressions once executable in a complete checkout.
- No GitHub Actions workflow was manually triggered or rerun.
- No production Grafana, Gemini, GCS, IAP, Cloud Logging, Secret Manager, operator, or remediation credentials/resources were touched.

### Decisions made

1. **Compose before replacing bootstrap defaults.** This closes the architectural gap between anchor restore and execution safety without immediately changing the production constructor path.
2. **Keep one `IncidentService` initialization.** Multiple inheritance is acceptable here only because both feature layers use cooperative `super()`; the explicit regression checks protect that assumption.
3. **Do not weaken execution uncertainty semantics for compaction.** Audit anchors reduce verification history, not provider-side safety requirements.
4. **Do not trigger CI merely to validate this increment.** The repository has a history of noisy Actions/storage usage; manual workflow execution remains avoided.

### Current blockers / unknowns

- The new composition has not yet executed in a complete repository checkout, so import/MRO behavior is regression-covered but not claimed green.
- `bootstrap.py` and `cloudrun_entrypoint.py` still instantiate `ExecutionSafeIncidentService` rather than `AnchoredExecutionSafeIncidentService`.
- The JSONL bootstrap sink still constructs `JsonlAuditLog`; production activation of anchors requires using `AnchoredJsonlAuditLog` for the local durable path or otherwise supplying an anchor-capable reader.
- Real Cloud Run/IAP browser acceptance, live Grafana MCP acceptance, production GCS generation/IAM validation, Cloud Logging schema-v4 suffix restore, and a real remediation provider remain external-resource validation tasks.

## Single best next step

**Switch the default bootstrap composition to `AnchoredExecutionSafeIncidentService` and use `AnchoredJsonlAuditLog` for the JSONL backend, add a bounded `--audit-anchor-interval` configuration with a conservative default, then extend bootstrap/Cloud Run tests to prove local v4 compaction restart and production GCS+Cloud Logging constructor wiring without triggering a live workflow or touching real credentials.**

## Previous run summary

The previous run added `AnchoredIncidentService` and `AnchoredJsonlAuditLog`, including schema-v4 anchor promotion, bounded suffix restore, physical-prefix-compaction coverage, post-anchor tamper rejection, and save-before-promote CAS safety, while intentionally leaving production bootstrap on the established execution-safe service.

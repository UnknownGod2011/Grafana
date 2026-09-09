# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the runtime evidence and observability plane. The executable path includes configurable Prometheus/Loki/Grafana MCP evidence, deterministic diagnosis, revision-bound Gemini briefing, authenticated approval-gated remediation, Grafana recovery verification, durable checkpointing with optimistic concurrency, provider reconciliation, Cloud Run/IAP deployment, operator readiness/metrics, a same-origin recovery cockpit, execution-safe dispatch barriers, tamper-evident audit chaining, checkpoint schema v3 audit-chain binding, hardened audit-integrity readiness policy, authenticated winning-lineage selection for multi-writer append-before-CAS audit streams, and a schema-v4 authenticated audit-anchor checkpoint contract.

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
- Authenticated audit-anchor primitive, Cloud Logging post-anchor candidate-range reads, and schema-v4 anchor persistence contract.

## Run log — 2026-09-09 — authenticated audit-anchor checkpoint schema

### Inspected at start

Read `progress.md` completely before choosing work. Inspected current `main`, `runtime/incident_checkpoint.py`, `runtime/incident_service.py`, `runtime/audit_anchor.py`, and existing checkpoint regression coverage. Confirmed the previous blocker: anchors existed only as an in-memory verification primitive and could not yet be authenticated inside durable checkpoint state.

### Exact changes made

1. Extended `runtime/incident_checkpoint.py` with backward-compatible schema v4.
   - Added `audit_anchor_sequence` and `audit_anchor_head_sha256` to `IncidentCheckpoint`.
   - Added `SCHEMA_V4 = stageguard.incident-checkpoint.v4` and made it the latest schema identifier.
   - Existing unbound checkpoints still serialize as v2; audit-chain-only checkpoints still serialize as v3; v4 is emitted only when a complete anchor pair is supplied.
   - Added shared validation for chain points and enforced complete sequence/head pairs, lowercase 64-hex digests, genesis digest rules, anchor-requires-chain, `anchor_sequence <= audit_chain_sequence`, and identical heads when anchor and current chain share a sequence.
   - Parsing remains compatible with v1/v2/v3 and now accepts authenticated v4 documents without changing older field sets.
   - The existing public SHA-256 plus optional HMAC envelope covers both anchor fields, so anchor mutation cannot be made authoritative by recomputing only the unauthenticated digest.
2. Added `runtime/tests/test_audit_anchor_checkpoint_schema.py`.
   - Covers signed v4 round-trip, anchor-without-chain rejection, partial-pair rejection, anchor-ahead-of-chain rejection, same-sequence conflicting-head rejection, v3 fallback when no anchor exists, and authenticated anchor tamper detection.
3. Preserved the current safety model.
   - The anchor remains a bounded verification/compaction boundary; the current authenticated chain head remains the commit marker.
   - No runtime restore path trusts the new fields yet, so this change cannot accidentally weaken existing genesis-based verification before the next integration increment.

### Tests / checks / results

- Repository inspection and Git object writes succeeded through the connected GitHub integration.
- A fresh local clone was attempted and still failed before Python started because the execution container could not resolve `github.com`; therefore no local Python green result is claimed for this run.
- No GitHub Actions workflow was manually triggered or rerun.
- No production Grafana, Gemini, GCS, IAP, Cloud Logging, Secret Manager, operator, or remediation credentials/resources were touched.

### Decisions made

1. **Schema v4 is explicit rather than silently changing v3.** Existing v3 documents retain their exact field contract and parser compatibility.
2. **Anchor fields are optional at the dataclass level but atomic at serialization.** A partial anchor can never be emitted.
3. **An anchor cannot exist without the current authenticated audit-chain head.** This prevents it from becoming an independent lifecycle authority.
4. **Equal anchor/current sequence requires equal digest.** A checkpoint cannot authenticate two conflicting histories at the same sequence.
5. **Runtime integration remains a separate step.** Until `IncidentService` rolls and consumes anchors, restart keeps the existing conservative behavior.

### Current blockers / unknowns

- `IncidentService` does not yet populate or consume the schema-v4 anchor fields, so production restart still verifies from genesis.
- `JsonlAuditLog.read_candidates` still lacks an exclusive lower bound; the Cloud Logging reader already supports it.
- The execution container still cannot resolve `github.com`, so the new Python tests have not executed in a complete local checkout during this run.
- Real Cloud Run/IAP browser acceptance, live Grafana MCP acceptance, production GCS generation/IAM validation, and a real remediation provider remain external-resource validation tasks.

## Single best next step

**Wire schema-v4 anchors into `IncidentService`: keep an authenticated in-memory anchor, roll it only after verified committed progress, persist it on every checkpoint, request durable candidates with `after_sequence=anchor.sequence`, add the same ranged candidate contract to `JsonlAuditLog`, and prove restart remains `verified` after physically deleting all pre-anchor JSONL records while post-anchor mutation, anchor substitution, and stale approval/remediation loser branches remain fail-closed or unauthoritative.**

## Previous run summary

The previous run added the authenticated audit-anchor primitive, bounded suffix verifier, and Cloud Logging `after_sequence` candidate-range support so StageGuard can eventually decouple restart availability from an incident's full historical audit prefix.

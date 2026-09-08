# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the runtime evidence and observability plane. The executable path includes configurable telemetry mapping, Prometheus/Loki/Grafana MCP evidence, deterministic diagnosis, revision-bound Gemini briefing, authenticated approval-gated remediation, Grafana recovery verification, signed checkpoint persistence with optimistic concurrency, provider idempotency reconciliation, Cloud Run/IAP deployment, operator readiness/metrics, a same-origin recovery cockpit, checkpoint schema v2 execution phases, bounded reconciliation reasons, append-only reconciliation audit events, deterministic tamper-evident audit chaining, checkpoint schema v3 audit-chain binding, restore-time audit verification, explicit audit-integrity observability, hardened audit-integrity readiness policy, operator-facing integrity migration guidance, legacy-v2 to verified-v3 migration acceptance, and a bounded committed-lineage verifier for multi-writer append-before-CAS audit streams.

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
- The authenticated checkpoint audit sequence/head is authoritative; unauthenticated audit records cannot manufacture lifecycle state.
- Committed-lineage verification is bounded so competing-writer floods fail closed rather than causing unbounded CPU/memory work.
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
- Durable checkpoint recovery, CAS conflict handling, operator recovery cockpit, execution phases, crash/SIGKILL ambiguity coverage, reconciliation reason model, bounded reconciliation audit events, tamper-evident audit chain, schema-v3 binding, restore-time audit verification, integrity observability/policy, operator integrity-policy safety, and hardened legacy migration acceptance.

## Run log — 2026-09-09 — committed-lineage verifier foundation

### Inspected at start

Read `progress.md` completely before choosing work. Inspected current `main`, `runtime/incident_service.py`, `runtime/incident_checkpoint.py`, `runtime/audit_integrity.py`, and `runtime/tests/test_runtime_audit_checkpoint_binding.py`. Confirmed the previous handoff's highest-priority production gap: audit append intentionally precedes checkpoint CAS, so a crashed or losing multi-instance writer can leave a same-sequence competitor or later orphan event. Current restore rejects those safely, but this can poison availability even when the authenticated v3 checkpoint already identifies the winning chain head.

### Exact changes made

1. Extended `runtime/audit_integrity.py` with `verify_committed_audit_lineage(...)`.
   - Treats the authenticated `AuditChainCheckpoint(sequence, head_sha256)` as the commit marker.
   - Groups durable candidates by sequence and searches only contiguous lineages capable of producing the authenticated head.
   - Ignores records beyond the authenticated sequence as uncommitted tails.
   - Allows same-sequence competing events only when a complete path still reproduces the authenticated head.
   - Preserves fail-closed deletion/mutation detection: if the committed event is removed or changed, no path can reproduce the authenticated head.
   - Supports restart from a previously trusted intermediate checkpoint.
   - Adds hard bounds of 32 candidate events per sequence and 128 concurrent lineage states by default; exceeding either bound fails closed.
2. Added `runtime/tests/test_committed_audit_lineage.py`.
   - Covers winner selection independent of append order.
   - Covers ignored post-head orphan tails.
   - Covers competing multi-sequence branches.
   - Covers committed-event mutation and deletion rejection.
   - Covers candidate/state explosion rejection.
   - Covers continuation from a trusted intermediate chain checkpoint.

### Tests / checks / results

- Repository reads and source writes succeeded through the GitHub connector.
- A fresh local clone was attempted again and failed before Python started because the execution container could not resolve `github.com`; the new tests are therefore **not claimed green locally**.
- No GitHub Actions workflow was manually triggered or rerun, avoiding CI/storage noise.
- No production Grafana, Gemini, GCS, IAP, Cloud Logging, Secret Manager, operator, or remediation credentials/resources were touched.

### Decisions made

1. **Do not introduce another checkpoint schema merely to name a writer.** The authenticated v3 chain head already cryptographically identifies the committed lineage and is a stronger commit marker than an unauthenticated writer ID.
2. **Unauthenticated tails are not lifecycle authority.** Records after the authenticated head may be retained for forensic/compaction purposes but must not advance restored incident state, approval, remediation, or sequence.
3. **Availability must not weaken integrity.** The verifier tolerates benign branch residue only when the exact authenticated head is reproducible; deletion or mutation of committed history still fails closed.
4. **Lineage resolution must be computationally bounded.** Excessive branch fan-out is treated as an integrity/DoS condition rather than permitting exponential search.

### Current blockers / unknowns

- The new committed-lineage verifier is implemented and tested in isolation but is not yet wired into `IncidentService._restore_audit_integrity`; current runtime restore therefore retains the previous conservative orphan-tail rejection behavior until that integration lands.
- The new tests still need execution in a complete checkout before a green result can be claimed.
- Cloud Logging pagination/order semantics need to be checked before using this verifier against production audit reads; the reader must expose all bounded candidates for a committed sequence rather than silently dropping same-sequence competitors across page boundaries.
- Real Cloud Run/IAP browser acceptance, live Grafana MCP acceptance, production GCS generation/IAM validation, and a real remediation provider remain external-resource validation tasks.

## Single best next step

**Wire `verify_committed_audit_lineage` into `IncidentService` restore/reload and committed timeline reads, replacing unconditional orphan-tail poisoning for authenticated schema-v3 checkpoints. Add concurrent-writer acceptance tests that leave both same-sequence and post-head loser events, prove restart remains `verified`/ready on the winning checkpoint, prove stale approval/remediation is never adopted or replayed, and keep legacy-unbound restore conservative until it has an authenticated v3 head.**

## Previous run summary

The previous run added a credential-free end-to-end migration acceptance test covering real schema-v2 persistence, hardened-unready legacy restore, a legitimate lifecycle write sealing authenticated schema v3, and a fresh verified-ready restart with sequence continuity and zero remediation calls.

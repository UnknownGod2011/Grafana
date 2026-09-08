# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the runtime evidence and observability plane. The executable path includes configurable telemetry mapping, Prometheus/Loki/Grafana MCP evidence, deterministic diagnosis, revision-bound Gemini briefing, authenticated approval-gated remediation, Grafana recovery verification, signed checkpoint persistence with optimistic concurrency, provider idempotency reconciliation, Cloud Run/IAP deployment, operator readiness/metrics, a same-origin recovery cockpit, checkpoint schema v2 execution phases, bounded reconciliation reasons, append-only reconciliation audit events, deterministic tamper-evident audit chaining, checkpoint schema v3 audit-chain binding, restore-time audit verification, explicit audit-integrity observability, hardened audit-integrity readiness policy, operator-facing integrity migration guidance, legacy-v2 to verified-v3 migration acceptance, and authenticated committed-lineage selection for multi-writer append-before-CAS audit streams.

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
- Same-sequence competitors and post-head loser records are tolerated only when the exact authenticated chain head is reproducible.
- Operator timelines use only the authenticated committed lineage after verified restore; loser audit residue remains forensic data and is not lifecycle authority.
- Committed-lineage verification and candidate retrieval are bounded so competing-writer floods fail closed rather than causing unbounded CPU/memory work.
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
- Durable checkpoint recovery, CAS conflict handling, operator recovery cockpit, execution phases, crash/SIGKILL ambiguity coverage, reconciliation reason model, bounded reconciliation audit events, tamper-evident audit chain, schema-v3 binding, restore-time audit verification, integrity observability/policy, operator integrity-policy safety, hardened legacy migration acceptance, bounded branched-lineage verification, and authenticated winning-lineage runtime restore.

## Run log — 2026-09-09 — authenticated winning-lineage runtime integration

### Inspected at start

Read `progress.md` completely before choosing work. Inspected `runtime/incident_service.py`, `runtime/audit_integrity.py`, `runtime/durable_audit_reader.py`, `runtime/execution_safety.py`, `runtime/tests/test_runtime_audit_checkpoint_binding.py`, and `runtime/tests/test_durable_audit_reader.py`. Confirmed the previous handoff gap: the committed-lineage verifier existed only as an isolated primitive while runtime restore still rejected any same-sequence competitor or post-head tail, causing an authenticated checkpoint winner to lose availability because of benign append-before-CAS residue.

### Exact changes made

1. Extended `runtime/audit_integrity.py` with `select_committed_audit_lineage(...)`.
   - Uses bounded dynamic programming and back-pointers to return the exact event path reproducing the authenticated schema-v3 chain head.
   - Keeps the existing 32-candidates-per-sequence and 128-concurrent-state bounds.
   - Ignores events beyond the authenticated sequence and fails closed on missing/mutated committed history.
   - `verify_committed_audit_lineage(...)` now delegates to the selector so verification and path selection share one implementation.
2. Added bounded candidate reads to both durable-reader paths.
   - `JsonlAuditLog.read_candidates(...)` scans the local append-only file while preserving same-sequence competitors and enforcing a 4096-event ceiling.
   - `GoogleCloudAuditReader.read_candidates(...)` issues a bounded Cloud Logging query for sequence `1..authenticated_head`, preserves conflicting same-sequence entries rather than collapsing them, consumes provider pagination through one bounded `max_results` request, and uses a sentinel result to fail closed instead of silently truncating.
   - The normal `read(...)` method remains conservative and still rejects conflicting same-sequence records for ordinary timeline consumers that do not have an authenticated lineage context.
3. Wired authenticated lineage selection into `IncidentService._restore_audit_integrity`.
   - Schema-v3 checkpoints use candidate-aware selection when the reader supports it.
   - Same-sequence loser events no longer poison restart if the exact signed/HMAC-authenticated checkpoint head is reproducible.
   - Post-head records are not adopted and cannot advance sequence, approval, outcome, or incident state.
   - Legacy/unbound restore deliberately keeps the older conservative tail rejection because it lacks an authenticated head capable of selecting a winner.
   - Readers that do not implement candidate enumeration also retain the older conservative behavior.
4. Made operator timelines committed-lineage aware.
   - Verified restore caches only the selected authenticated history.
   - A CAS-losing audit append is no longer added to the in-process committed timeline before checkpoint save succeeds.
   - New winner events are added to committed history only after checkpoint persistence succeeds.
5. Aligned `ExecutionSafeIncidentService._record_reconciliation_attempt` with the same commit rule.
   - Reconciliation attempts still append before the `dispatching` checkpoint as required for audit durability.
   - They become operator-visible committed history only after the phase-preserving checkpoint save succeeds.
   - A reconciliation CAS loser therefore remains durable forensic residue but cannot leak into the winner timeline.
6. Updated credential-free regression coverage.
   - `test_runtime_audit_checkpoint_binding.py` now proves a post-head orphan approval is not adopted, does not call remediation, does not appear in the timeline, and does not prevent a legitimate winner from reusing that sequence and surviving another verified restart.
   - The same suite now proves a conflicting duplicate at the authenticated sequence is tolerated only because the exact committed event remains reproducible.
   - `test_durable_audit_reader.py` now covers Cloud Logging candidate filters, preservation of same-sequence competitors, and fail-closed result-bound exhaustion.

### Tests / checks / results

- Repository reads and all source/test writes succeeded through the GitHub connector.
- A fresh local clone was attempted and still failed before Python started because the execution container could not resolve `github.com`; therefore **no local Python test result is claimed** for this run.
- GitHub reports no status contexts on the latest source/test commit at the time checked. No GitHub Actions workflow was manually triggered or rerun, avoiding CI/storage noise.
- No production Grafana, Gemini, GCS, IAP, Cloud Logging, Secret Manager, operator, or remediation credentials/resources were touched.

### Decisions made

1. **The authenticated v3 head is the commit marker.** Append order alone is not authority in a multi-writer stream.
2. **Legacy state stays conservative.** `unbound_legacy` cannot safely distinguish a real event from a losing writer, so branch tolerance is enabled only when an authenticated chain head exists.
3. **Candidate enumeration must be explicit.** The ordinary `read(after_sequence=...)` API can collapse or paginate away same-sequence branches; verified restore therefore uses a separate bounded candidate-read contract.
4. **No silent truncation.** If candidate retrieval exceeds the configured bound, integrity fails closed rather than verifying a partial stream.
5. **Operator history is committed history.** Durable loser records remain available for forensics/compaction but cannot manufacture approval, remediation, recovery, or timeline state.
6. **Do not weaken exactly-once remediation guarantees for availability.** No loser approval is replayed and provider execution is never triggered during lineage restoration.

### Current blockers / unknowns

- The execution container still cannot resolve `github.com`, so the changed Python suite has not run in a complete local checkout during this run.
- Cloud Logging candidate reads are intentionally capped at 4096 entries and bounded by the configured logging lookback. A sufficiently long-lived/high-churn incident can therefore become fail-closed even with intact history unless StageGuard introduces authenticated audit anchors/compaction or an equivalent bounded-history checkpoint mechanism.
- The current Cloud Logging behavior is covered with a fake logger, not a live Google Cloud project; real pagination/filter/IAM acceptance remains an external-resource validation task.
- Real Cloud Run/IAP browser acceptance, live Grafana MCP acceptance, production GCS generation/IAM validation, and a real remediation provider remain external-resource validation tasks.

## Single best next step

**Add authenticated audit anchors/compaction so production restart can verify only a bounded suffix from a trusted intermediate chain checkpoint instead of replaying the entire incident history. The design must preserve the current v3 winner-lineage semantics, make Cloud Logging lookback/4096-result limits operationally safe, reject anchor deletion or substitution, and include restart tests with competing pre-anchor and post-anchor writer residue without allowing stale approval or remediation replay.**

## Previous run summary

The previous run added the bounded committed-lineage verifier primitive but had not yet wired it into runtime restore, Cloud Logging candidate retrieval, or operator timeline selection.

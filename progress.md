# StageGuard Progress

## Current status

StageGuard is a personal open-source incident commander for live media workflows. The executable path now includes configurable telemetry mapping, Prometheus/Loki/Grafana MCP evidence, deterministic diagnosis, revision-bound Gemini briefing, authenticated approval-gated remediation, Grafana recovery verification, signed checkpoint persistence with optimistic concurrency, provider idempotency reconciliation, Cloud Run/IAP deployment, operator readiness/metrics, a same-origin recovery cockpit, checkpoint schema v2 with a durable pre-side-effect remediation phase, and bounded reconciliation audit events.

Core safety invariants:

- Grafana is the evidence plane; infrastructure write credentials remain isolated from Grafana/MCP access.
- Gemini is advisory and cannot mutate approval, remediation, or recovery state.
- Human approval is single-use and bound to an exact evidence revision.
- Production remediation uses a deterministic idempotency identity and never automatically replays ambiguous external side effects.
- Phase-capable stores persist `dispatching` before provider contact; restored `dispatching` and legacy ambiguous approvals require provider reconciliation plus fresh Grafana evidence.
- GCS checkpoints are HMAC-authenticated and use generation compare-and-swap.
- `/readyz` fails closed for checkpoint conflict or execution uncertainty; execution phase and reconciliation reason telemetry are fixed-cardinality and provider-detail-free.
- Concrete remediation reconciliation is GET-only and cannot carry a remediation body.
- Reconciliation audit entries contain only bounded result/reason dimensions; provider payloads, operation IDs, endpoints, credentials, generations, and raw exceptions are excluded.
- Reconciliation audit persistence must never regress the durable `dispatching` barrier back to `approved`.

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
- Checkpoint schema v2 phases: `none`, `approved`, `dispatching`, `resolved`, with conservative legacy restore.
- Crash-boundary and real SIGKILL acceptance across dispatch/provider boundaries.
- Real loopback TLS coverage for `HttpRemediationTransport` execution and GET-only reconciliation.
- Concrete HTTPS restart coverage for malformed, wrong-operation, unknown-state, and timeout reconciliation outcomes, including later authoritative recovery.
- Credential-free spawned-process GCS generation-CAS acceptance and service-level multi-instance dispatch/reconciliation races.
- Fixed-cardinality reconciliation-reason model in operator state, readiness, Prometheus telemetry, cockpit guidance, conflict matrices, and concrete crash/HTTPS tests.
- Append-only bounded reconciliation-attempt and recovery audit events integrated into the governed audit stream.

## Run log — 2026-09-08 — bounded reconciliation audit trail

### Inspected at start

Read `progress.md` completely before deciding what to change. Then inspected:

- `runtime/execution_safety.py` for provider reconciliation, durable `dispatching`, uncertainty reasons, and recovery flow;
- `runtime/incident_service.py` for the append-only audit pipeline, timeline projection, sequencing, and checkpoint coupling;
- `runtime/cloud_audit.py` for structured Cloud Logging validation and blocked sensitive field classes;
- `runtime/incident_checkpoint.py` for schema-v2 execution-phase derivation and validation;
- existing reconciliation observability tests and current repository status.

### Exact changes made

1. Extended `runtime/execution_safety.py` with bounded reconciliation audit events.
   - Every provider reconciliation read now records an append-only attempt containing only `result` (`accepted`, `not_found`, `unknown`) and the existing bounded reconciliation reason.
   - Successful authoritative reconciliation records a second recovery event only after fresh Grafana investigation succeeds.
   - Operator-visible event types encode only the bounded stage/result/reason dimensions, so the existing timeline remains useful without exposing provider details.
   - Invalid stage/result/reason inputs fail closed to bounded fallback values.

2. Preserved the durable dispatch barrier while auditing uncertainty.
   - The generic lifecycle recorder derives checkpoint phase from the pending approval and would therefore serialize `approved` during an uncertain reconciliation attempt.
   - The new reconciliation-attempt recorder detects phase-capable stores and explicitly persists schema-v2 `dispatching` with the incremented audit sequence.
   - CAS conflict while recording the audit event marks the service conflicted, clears the reloaded flag, and remains execution-uncertain; it does not enable replay.
   - Phase-unaware/custom stores retain their existing conservative restart behavior.

3. Added `runtime/tests/test_execution_reconciliation_audit.py`.
   - Verifies exact bounded payload shape and provider-operation redaction.
   - Verifies audit sequencing advances while the checkpoint remains `dispatching`.
   - Verifies CAS conflict fails closed.
   - Verifies `unknown` produces an attempt event but no recovery event and leaves uncertainty intact.
   - Verifies authoritative `accepted` produces attempt + recovery events and clears uncertainty only after the modeled fresh-investigation success.
   - Verifies malformed audit dimensions collapse to bounded fallbacks rather than leaking arbitrary strings.

### Tests / checks / results

- GitHub repository reads and writes succeeded.
- Source commits created in this run:
  - `efdda8bce890b6fa45056aac688fb63e204ac2ff` — reconciliation audit implementation.
  - `3a16023cea1bdb45e80f703ff6981b6e290bcd02` — targeted audit safety tests.
- GitHub combined status for `3a16023cea1bdb45e80f703ff6981b6e290bcd02` reports zero status contexts; no GitHub Actions workflow was intentionally triggered or rerun.
- A direct local checkout/test attempt is still blocked before Python starts because the container cannot resolve `github.com`; therefore the new suite is **not claimed green locally**.
- No Grafana, Gemini, GCS, IAP, Cloud Logging, Secret Manager, operator, or production remediation credentials/resources were used.

### Decisions made

1. **Auditability cannot weaken dispatch safety.** Reconciliation audit sequence persistence explicitly retains `dispatching` on phase-capable stores.
2. **Audit dimensions are enums, not provider data.** Event payloads and operator-visible event types contain only bounded result/reason/stage values.
3. **`unknown` is itself auditable.** Failed, malformed, or timed-out provider reads leave an append-only attempt trail while remaining reconciliation-gated.
4. **Recovery is audited only after fresh Grafana evidence succeeds.** A successful provider GET alone is not considered recovery completion.
5. **No new metric labels were introduced.** The audit trail improves diagnosis without increasing Prometheus cardinality.

### Current blockers / unknowns

- The new targeted test file still needs execution in a complete local/CI checkout before a green result can be claimed.
- Real GCS generation behavior still needs live/emulated provider-backed acceptance beyond the credential-free generation-aware fake.
- Real Cloud Run/IAP browser acceptance, live Grafana MCP acceptance, real GCS acceptance, and a real remediation provider remain external-resource validation tasks.

## Single best next step

**Extend the concrete SIGKILL/HTTPS ambiguity suites to assert the new append-only audit sequence end-to-end: one bounded `unknown` attempt per malformed/wrong-operation/timeout reconciliation call, one bounded authoritative attempt plus one recovery event after fresh Grafana evidence, durable sequence monotonicity across restart, and still exactly one remediation POST.**

## Previous run summary

The previous run bound reconciliation reasons to real SIGKILL and HTTPS ambiguity paths, requiring `durable_dispatching` while unsafe and `clear` only after authoritative reconciliation plus fresh Grafana evidence.

# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the runtime evidence and observability plane. The executable path includes configurable Prometheus/Loki/Grafana MCP evidence, deterministic diagnosis, revision-bound Gemini briefing, authenticated approval-gated remediation, Grafana recovery verification, durable checkpointing with optimistic concurrency, provider reconciliation, Cloud Run/IAP deployment, operator readiness/metrics, a same-origin recovery cockpit, execution-safe dispatch barriers, tamper-evident audit chaining, checkpoint schema v3 audit-chain binding, hardened audit-integrity readiness policy, authenticated winning-lineage selection for multi-writer append-before-CAS audit streams, schema-v4 authenticated audit-anchor checkpoints, and an anchor-aware incident-service/runtime layer for bounded-suffix restore.

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
- Authenticated audit-anchor primitive, Cloud Logging post-anchor candidate-range reads, schema-v4 anchor persistence contract, and an executable anchor-aware JSONL/runtime service layer.

## Run log — 2026-09-09 — anchor-aware runtime integration layer

### Inspected at start

Read `progress.md` completely before choosing work. Inspected current `main`, `runtime/incident_service.py`, `runtime/incident_checkpoint.py`, `runtime/audit_anchor.py`, current audit-binding tests, and the durable checkpoint stores. Confirmed the highest-value unblocked gap: schema-v4 anchor fields existed, but the stable runtime still verified from genesis and local JSONL candidate enumeration had no exclusive lower bound.

### Exact changes made

1. Added `runtime/anchored_incident_service.py` as a backward-compatible integration layer rather than weakening the stable runtime in one step.
   - Added `AnchoredJsonlAuditLog`, which preserves same-sequence competitors but constrains candidate enumeration to `after_sequence < sequence <= through_sequence` with the existing 4096-result bound.
   - Added `AnchoredIncidentService`, which consumes authenticated schema-v4 anchors, requests only post-anchor candidates, and verifies/selects the committed suffix with `select_anchored_committed_lineage(...)`.
   - Existing v2/v3/unanchored checkpoints delegate to the stable `IncidentService` restore path unchanged.
   - Anchor promotion uses `roll_audit_anchor(...)` and is included in the checkpoint being persisted, but the in-memory anchor is promoted only after the checkpoint save succeeds. CAS failure therefore cannot promote a losing writer's anchor.
   - Before the configured interval is reached, the service remains on v3 instead of emitting a schema-v4 checkpoint with a meaningless genesis anchor.
   - Added bounded operator-safe `audit_anchor_state()` metadata without exposing event payloads or actor identities.
2. Added `runtime/tests/test_anchored_incident_runtime.py`.
   - Covers exclusive JSONL lower-bound reads.
   - Covers schema-v4 emission after anchor promotion and verified restart after physically deleting all audit records at/before the authenticated anchor.
   - Covers post-anchor committed-event mutation failing closed after the compactable prefix is removed.
   - Covers checkpoint CAS conflict leaving the proposed anchor unauthenticated/unpromoted in memory.
3. Kept deployment wiring unchanged for this increment.
   - The new layer is executable and regression-covered, but `bootstrap.py` / `cloudrun_entrypoint.py` still instantiate the stable service. This deliberately keeps rollout reversible until the integration tests can be executed in a complete checkout.

### Tests / checks / results

- Both new Python files were syntax-compiled successfully in the execution environment with `py_compile` before being written to GitHub.
- A fresh repository clone was attempted again and failed before Python/test execution because the container still cannot resolve `github.com`; therefore no full-suite or import-time green result is claimed.
- GitHub repository reads and Git-object writes succeeded through the connected GitHub integration.
- No GitHub Actions workflow was manually triggered or rerun.
- No production Grafana, Gemini, GCS, IAP, Cloud Logging, Secret Manager, operator, or remediation credentials/resources were touched.

### Decisions made

1. **Integrate anchors behind a subclass first.** This gives us an executable bounded-suffix path while keeping the already-hardened stable `IncidentService` behavior unchanged until complete test execution is possible.
2. **Do not authenticate genesis just to force schema v4.** The service stays v3 until a real interval-based anchor promotion occurs.
3. **Save-before-promote is mandatory.** A proposed anchor is not trusted in memory until the same checkpoint carrying it is durably accepted.
4. **Anchored restore requires a reader with an explicit lower-bound contract.** A reader that cannot prove ranged enumeration fails closed rather than silently fetching/filtering an incomplete prefix.
5. **Compaction never changes lifecycle authority.** The current authenticated audit-chain head remains the commit marker; the anchor only establishes the verified starting state for reproducing that head.

### Current blockers / unknowns

- The execution container still cannot resolve `github.com`, so the new integration tests have not executed with the repository's real import path/dependencies.
- `bootstrap.py`, `cloudrun_entrypoint.py`, and execution-safe service composition do not yet select `AnchoredIncidentService`; production remains on the stable genesis-verification path.
- The anchor-aware layer has not yet been exercised against a real GCS+Cloud Logging deployment; those remain external-resource validation tasks.
- Real Cloud Run/IAP browser acceptance, live Grafana MCP acceptance, production GCS generation/IAM validation, and a real remediation provider remain external-resource validation tasks.

## Single best next step

**Run the anchored runtime regression suite in a complete checkout, fix any integration/import defects, then fold the proven lower-bound and anchor lifecycle behavior into the default `IncidentService` / execution-safe composition and Cloud Run bootstrap. After that, add a production acceptance case covering GCS-authenticated schema-v4 state + Cloud Logging suffix restore, including stale loser branches and no remediation replay.**

## Previous run summary

The previous run added the backward-compatible schema-v4 checkpoint contract carrying authenticated audit-anchor sequence/head state, while intentionally leaving runtime restore on the existing genesis-based verifier.

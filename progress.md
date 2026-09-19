# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the read-only runtime evidence plane. The implemented vertical slice includes deterministic telemetry, Prometheus/Loki/Grafana, official Grafana MCP access, bounded investigation and diagnosis, optional Gemini briefing, exact-revision approval, remediation adapters, telemetry-verified recovery, authenticated lifecycle state, checkpoint/audit integrity, operator UI, Cloud Run deployment hardening, watchdog observability, authenticated private metrics bridging, evidence-unavailable abstention, no-replay execution reconciliation, recovery-only Grafana rechecks, stdio-only Grafana MCP launchers, strict operator-API authentication/framing/protocol preflight, and a loopback reference remediation provider with idempotent writes plus read-only operation reconciliation.

## Core invariants

- Grafana/MCP is read-only evidence access; infrastructure-write credentials remain isolated.
- Gemini is advisory and cannot mutate diagnosis, approval, remediation, or recovery state.
- Required evidence unavailability prevents briefing, approval, and execution from becoming actionable.
- Approval is exact-revision-bound and single-use; provider acceptance never counts as recovery.
- Fresh Grafana telemetry is required to verify recovery; `recovery_unverified` cannot replay remediation.
- Ambiguous remediation execution remains behind the execution-uncertainty barrier until durable reconciliation and fresh evidence resolve it.
- Operator API and reference remediation provider reject ambiguous credential/body framing before mutation.
- Production remediation accepts only canonical operation IDs, canonical bounded target identities at configuration/runtime boundaries, construction-frozen execution and reconciliation capabilities, an exact `TransportResult` execution-result type with strictly validated fields, strictly validated reconciliation states, and bounded finite policy configuration. Provider descriptor faults fail closed.
- Cloud Logging audit filters treat incident/log identifiers as bounded literals and reject raw control characters before issuing queries.
- Consolidated validation is credential-isolated, timeout-bounded, non-interactive, and tracks safe runtime-test ownership explicitly.

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected Windows-specific permission test skipped.
- Focused core/API/UI suite from the last executable repository run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating latest hardening/recovery work.
- Historical official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`; pinned `1.4.1` still requires a live smoke.
- Current connector-authored changes have not been repository-executed in this runner and are not treated as passing tests.

## Latest run — 2026-09-19 — reconciliation capability freeze

### Inspected at start

Read `progress.md` completely first, then inspected `runtime/production_remediation.py`, `runtime/tests/test_production_remediation.py`, and `runtime/tests/test_validation_remediation_boundary.py`. The mutation callable had already been frozen at construction, but reconciliation still re-read the provider-controlled `reconcile` descriptor on every uncertainty-barrier check. Because reconciliation participates in StageGuard's durable no-replay decision, this left a check/use inconsistency: a mutable descriptor could change reconciliation behavior between calls.

### Changes / actions

- Production remediation now resolves the optional provider `reconcile` capability once during construction and freezes the resulting bound callable alongside `execute`.
- A raising or non-callable reconciliation descriptor is treated as unavailable; all subsequent reconciliation checks deterministically return `unknown` without re-reading provider-controlled attributes.
- `reconcile_operation` now invokes only the frozen capability and retains exact operation-ID validation, exception containment, exact-string state validation, and the closed `accepted` / `not_found` protocol.
- Added a mutable reconciliation descriptor regression proving two reconciliation checks use one descriptor lookup while invoking the same captured callable twice.
- Strengthened the raising reconciliation descriptor regression to prove the hostile descriptor is resolved once and is never retried during later incident-state checks.
- No credentials, live remediation targets, Grafana instances, Docker, cloud resources, GitHub Actions, or unrelated repositories were touched.

### Checks / results

- Runtime reconciliation hardening committed as `30dac8e58e9dca408f42e00adce0f133aecd9955`.
- Validation-owned regressions committed as `9ccda7f50a4ec0665e0710eb95654d6abcef48b3`.
- Static inspection confirms `reconcile_operation` uses `self._reconcile` and performs no provider attribute lookup.
- No green execution claim is made: this connector runner can modify and inspect repository files but does not provide an executable checkout for the Python suite.

### Decisions

1. Provider reconciliation is read-only but security-critical because it controls whether StageGuard may resolve an ambiguous production mutation without replaying it.
2. Provider capabilities are frozen at construction so mutable descriptors cannot alter either mutation or uncertainty-reconciliation behavior after validation.
3. Optional reconciliation remains fail-closed: absence, malformed capability, descriptor faults, call faults, or malformed states all map to `unknown`.
4. Regression coverage remains in the existing consolidated remediation boundary rather than creating another CI surface.

### Blockers / unknowns

- The consolidated runner still requires execution in a real checkout; current connector-authored changes remain unexecuted here.
- Historical full-suite failures/errors still need classification from an executable checkout.
- Live Gemini acceptance remains intentionally credentialed and outside this dependency-light runner.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- Disposable private Cloud Run acceptance still requires suitable credentials/environment and Docker.

## Single best next step

Run `scripts/run_stageguard_validation.py --require-full-coverage --keep-going` in the first executable checkout and fix every concrete failure without weakening credential isolation, no-replay semantics, or frozen provider capabilities; then perform the pinned Grafana MCP 1.4.1 read-only smoke when Docker/Grafana access is available.

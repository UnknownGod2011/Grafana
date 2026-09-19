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
- Production remediation accepts only canonical operation IDs, canonical bounded target identities at configuration/runtime boundaries, a construction-validated frozen execution callable, an exact `TransportResult` execution-result type with strictly validated fields, strictly validated reconciliation states, and bounded finite policy configuration. Provider descriptor faults fail closed.
- Cloud Logging audit filters treat incident/log identifiers as bounded literals and reject raw control characters before issuing queries.
- Consolidated validation is credential-isolated, timeout-bounded, non-interactive, and tracks safe runtime-test ownership explicitly.

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected Windows-specific permission test skipped.
- Focused core/API/UI suite from the last executable repository run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating latest hardening/recovery work.
- Historical official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`; pinned `1.4.1` still requires a live smoke.
- Current connector-authored changes have not been repository-executed in this runner and are not treated as passing tests.

## Latest run — 2026-09-19 — remediation transport callable-boundary hardening

### Inspected at start

Read `progress.md` completely first, then inspected the repository tree, `scripts/run_stageguard_validation.py`, `runtime/tests/test_stageguard_validation_runner.py`, `runtime/production_remediation.py`, `runtime/tests/test_production_remediation.py`, and `runtime/tests/test_validation_remediation_boundary.py`. The production adapter validated `transport.execute` during construction but re-read `self._transport.execute` during every mutation, leaving a mutable/provider-controlled descriptor able to change behavior after validation. Reconciliation also performed its `getattr(..., "reconcile")` outside the exception boundary.

### Changes / actions

- Production remediation now captures and freezes the validated bound `execute` callable during construction and invokes that callable for all mutation attempts instead of re-reading a provider-controlled attribute.
- Construction now converts an exception raised while resolving `transport.execute` into a bounded `ValueError`, rather than leaking arbitrary provider descriptor behavior.
- Reconciliation now includes lookup of the optional provider `reconcile` method inside the fail-closed exception boundary; a raising descriptor resolves to `unknown`.
- Added validation-owned regressions for a mutable `execute` descriptor, a raising `execute` descriptor, and a raising `reconcile` descriptor.
- The mutable-descriptor regression proves the execution attribute is resolved exactly once, while the captured callable still performs the accepted provider request.
- No credentials, live remediation targets, Grafana instances, Docker, cloud resources, GitHub Actions, or unrelated repositories were touched.

### Checks / results

- Runtime hardening committed as `5642c01975a2840ed710cc91ecc94de045ddee4d`.
- Boundary regressions committed as `e267f31b6b9d7ce154afceb032f606864d907f24`.
- Static inspection confirms the mutation path calls `self._execute(...)`, not `self._transport.execute(...)`, and reconciliation lookup is exception-bounded.
- No green execution claim is made: this connector runner can modify and inspect repository files but does not provide an executable checkout for the Python suite.

### Decisions

1. A production provider transport is an external trust boundary even after object construction; method lookup itself is not assumed inert.
2. The execution capability is frozen once after validation so mutable descriptors cannot create a check/use split at the mutation boundary.
3. Reconciliation remains optional, but malformed/raising provider lookup behavior maps to `unknown` rather than escaping the incident commander.
4. Regressions remain in the existing validation-owned remediation boundary to avoid adding CI surfaces.

### Blockers / unknowns

- The consolidated runner still requires execution in a real checkout; current connector-authored changes remain unexecuted here.
- Historical full-suite failures/errors still need classification from an executable checkout.
- Live Gemini acceptance remains intentionally credentialed and outside this dependency-light runner.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- Disposable private Cloud Run acceptance still requires suitable credentials/environment and Docker.

## Single best next step

Run `scripts/run_stageguard_validation.py --require-full-coverage --keep-going` in the first executable checkout and fix every concrete failure without weakening credential isolation, no-replay semantics, or the frozen provider-callable boundary; then perform the pinned Grafana MCP 1.4.1 read-only smoke when Docker/Grafana access is available.

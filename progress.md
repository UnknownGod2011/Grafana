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
- Production remediation accepts only canonical operation IDs, canonical bounded target identities, callable provider transports, an exact `TransportResult` execution-result type with strictly validated fields, strictly validated reconciliation states, and bounded finite policy configuration; malformed runtime identities/configuration fail closed before transport.
- Cloud Logging audit filters treat incident/log identifiers as bounded literals and reject raw control characters before issuing queries.
- Consolidated validation is credential-isolated, timeout-bounded, non-interactive, and tracks safe runtime-test ownership explicitly.

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected Windows-specific permission test skipped.
- Focused core/API/UI suite from the last executable repository run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating latest hardening/recovery work.
- Historical official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`; pinned `1.4.1` still requires a live smoke.
- Current connector-authored changes have not been repository-executed in this runner and are not treated as passing tests.

## Latest run — 2026-09-19 — exact provider result regression ownership

### Inspected at start

Read `progress.md` completely first, then inspected `runtime/production_remediation.py`, `scripts/run_stageguard_validation.py`, `runtime/tests/test_validation_remediation_boundary.py`, `runtime/tests/test_production_remediation.py`, and the repository tree. The prior run had correctly tightened the provider result boundary from `isinstance` to exact `TransportResult` type matching, but explicitly left the corresponding regression unresolved until its validation-owned test location could be identified.

### Changes / actions

- Resolved the existing validation ownership: `test_production_remediation.py` is already selected by the `remediation adapter boundary` gate in `scripts/run_stageguard_validation.py`, and the validation-boundary contract explicitly requires that file.
- Added `test_transport_result_subclass_is_rejected_without_retry` to `runtime/tests/test_production_remediation.py`.
- The regression supplies a provider-controlled subclass carrying an apparently successful `202` result and proves StageGuard rejects it, records exactly one provider attempt, preserves `transport_status=None`, and does not retry or transition to accepted state.
- Kept the test inside the existing owned policy suite rather than creating a new standalone test island.
- No CI workflow was added or triggered deliberately; no credentials, cloud resources, Docker, Grafana instances, remediation targets, or unrelated repositories were touched.

### Checks / results

- Regression committed as `735d10bf4dcc7b01dcb7101095c31a1123e0ba22`.
- Static inspection confirms the regression matches the exact-type check in `_valid_transport_result` and is owned by the consolidated remediation gate.
- No green execution claim is made because this connector environment does not expose an executable checkout. The new regression and the full validation runner still require repository execution.

### Decisions

1. The exact provider-result protocol is now both implemented and regression-specified in an already-owned validation file.
2. A provider result subclass that looks successful is deliberately treated as malformed execution evidence; it cannot become an accepted remediation result.
3. Security regressions should continue to be placed in existing validation-owned files whenever ownership is already defined.

### Blockers / unknowns

- The consolidated runner still requires execution in a real checkout.
- Historical full-suite failures/errors still need classification from an executable checkout.
- Live Gemini acceptance remains intentionally credentialed and outside this dependency-light runner.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- Disposable private Cloud Run acceptance still requires suitable credentials/environment and Docker.

## Single best next step

Run `scripts/run_stageguard_validation.py --require-full-coverage --keep-going` in the first available executable checkout and fix every concrete failure, starting with the remediation adapter boundary, without weakening credential isolation, no-replay remediation semantics, or validation ownership.

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
- Production remediation accepts only canonical operation IDs, canonical bounded target identities at both configuration and runtime boundaries, callable provider transports, an exact `TransportResult` execution-result type with strictly validated fields, strictly validated reconciliation states, and bounded finite policy configuration; malformed runtime identities/configuration fail closed before transport.
- Cloud Logging audit filters treat incident/log identifiers as bounded literals and reject raw control characters before issuing queries.
- Consolidated validation is credential-isolated, timeout-bounded, non-interactive, and tracks safe runtime-test ownership explicitly.

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected Windows-specific permission test skipped.
- Focused core/API/UI suite from the last executable repository run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating latest hardening/recovery work.
- Historical official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`; pinned `1.4.1` still requires a live smoke.
- Current connector-authored changes have not been repository-executed in this runner and are not treated as passing tests.

## Latest run — 2026-09-19 — hostile runtime remediation target regression

### Inspected at start

Read `progress.md` completely first, then inspected `runtime/production_remediation.py`, `runtime/tests/test_production_remediation.py`, `runtime/tests/test_validation_remediation_boundary.py`, and `scripts/run_stageguard_validation.py`. The previous run had hardened runtime target identities before equality comparison, but the explicit hostile-object regression was still missing.

### Changes / actions

- Added a regression to the already validation-owned remediation boundary contract using a caller-controlled object whose `__eq__` raises if invoked.
- Covered both hostile production-ID and hostile uplink positions. Each must be rejected as an unsupported target with zero provider attempts while preserving a valid operation ID only as bounded correlation metadata.
- Added malformed runtime-string cases for empty, surrounding whitespace, embedded control characters, and overlength identities, all requiring zero provider calls.
- Used a transport that raises if execution is attempted, so the regression proves malformed targets cannot cross the provider mutation boundary.
- Kept the test inside `test_validation_remediation_boundary.py`, which is already selected by both the validation-harness pattern and remediation-boundary ownership contract; no new unowned test file or CI workflow was introduced.
- No credentials, cloud resources, Docker, Grafana instances, remediation targets, GitHub Actions, or unrelated repositories were touched.

### Checks / results

- Regression committed as `6dd2dbef41c31af6766367aaad1d38dcbc2d4de2`.
- Static contract inspection confirms runtime target validation occurs before equality and before `transport.execute`.
- No green execution claim is made: this connector runner can modify and inspect repository files but does not provide an executable checkout for the Python suite.

### Decisions

1. Hostile-object behavior is tested directly rather than inferred from type annotations or implementation shape.
2. The regression asserts zero mutation attempts, making provider non-contact part of the safety contract.
3. Malformed canonical strings are covered alongside hostile objects because both enter through the same runtime trust boundary.

### Blockers / unknowns

- The consolidated runner still requires execution in a real checkout; current connector-authored changes remain unexecuted here.
- Historical full-suite failures/errors still need classification from an executable checkout.
- Live Gemini acceptance remains intentionally credentialed and outside this dependency-light runner.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- Disposable private Cloud Run acceptance still requires suitable credentials/environment and Docker.

## Single best next step

Run `scripts/run_stageguard_validation.py --require-full-coverage --keep-going` in the first executable checkout, classify and fix every concrete failure without weakening credential isolation/no-replay semantics, then perform the pinned Grafana MCP 1.4.1 read-only smoke when Docker/Grafana access is available.

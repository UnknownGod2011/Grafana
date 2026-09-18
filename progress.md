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
- Cloud Logging audit filters treat incident/log identifiers as bounded literals and reject raw control characters before issuing queries.
- Consolidated validation is credential-isolated, timeout-bounded, non-interactive, and tracks safe runtime-test ownership explicitly.

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected Windows-specific permission test skipped.
- Focused core/API/UI suite from the last executable repository run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating latest hardening/recovery work.
- Historical official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`; pinned `1.4.1` still requires a live smoke.
- Current connector-authored tests have not been repository-executed in this runner and are not treated as passing tests.

## Latest run — 2026-09-18 — validation harness ownership regression fix

### Inspected at start

Read `progress.md` completely first, then inspected `scripts/run_stageguard_validation.py`, `runtime/tests/test_stageguard_validation_runner.py`, and the runtime-test inventory exposed by the repository API.

### Changes / actions

- Fixed the pre-existing validator regression in `test_stageguard_validation_runner.py::test_validation_harness_gate_owns_runner_regressions`.
- The regression now matches the runner's intentional ownership model: the `validation harness` gate owns `test_stageguard_validation_runner.py` plus the `test_validation_*.py` ownership contracts.
- The assertion remains fail-closed about scope: every file selected by that gate must be either the runner regression itself or a `test_validation_*.py` contract, and at least one ownership contract must be present.
- This preserves the useful property that newly added validation-ownership regressions are automatically validated while preventing unrelated tests from silently entering the harness gate.
- No credentials, cloud resources, Docker, Grafana instances, remediation targets, GitHub Actions, or unrelated repositories were touched.

### Checks / results

- The inconsistent assertion identified in the previous run has been reconciled with the actual gate definition.
- Change committed as `7eea66a2d1e6c7a9313173cd679c99fac607aa5d`.
- No green test-run claim is made because this connector environment does not expose an executable checkout.

### Decisions

1. Keep `test_validation_*.py` as intentional validation-harness ownership rather than splitting every ownership contract into another meta-gate; these tests validate the validator itself and are dependency-light.
2. Make the regression verify both inclusion and scope instead of hard-coding a stale one-file set.
3. Continue treating `--require-full-coverage` as a release criterion only after execution in a real checkout confirms the current inventory and failures are classified.

### Blockers / unknowns

- The consolidated runner still requires execution in a real checkout.
- Historical full-suite failures/errors still need classification from an executable checkout.
- Live Gemini acceptance remains intentionally credentialed and outside this dependency-light runner.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- Disposable private Cloud Run acceptance still requires suitable credentials/environment and Docker.

## Single best next step

Audit the remaining currently unowned `runtime/tests/test_*.py` files and classify every dependency-light test into an exact or narrowly bounded gate while explicitly excluding genuinely live/credentialed acceptance tests; then run `scripts/run_stageguard_validation.py --require-full-coverage --keep-going` in the first available executable checkout and classify failures rather than weakening gates.

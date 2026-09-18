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

## Latest run — 2026-09-18 — Gemini validation ownership audit

### Inspected at start

Read `progress.md` completely first, then inspected the repository tree, `scripts/run_stageguard_validation.py`, `runtime/tests/test_stageguard_validation_runner.py`, and the previously unowned `runtime/tests/test_gemini_acceptance_smoke.py`.

### Changes / actions

- Classified `test_gemini_acceptance_smoke.py` explicitly under the `evidence and diagnosis` production-validation gate.
- This does **not** enable live Gemini calls. The test's subprocess path omits `--execute`; execute-path unit tests mock `_execute_smoke`, and the runner separately strips ambient Google/Gemini credentials and isolates ADC/gcloud homes.
- Repository tree review found the remaining runtime acceptance-named watchdog tests are already intentionally selected by the runtime-observability gate; fake-cloud restart acceptance is explicitly owned by cloud durability simulation.
- No credentials, cloud resources, Docker, Grafana instances, remediation targets, GitHub Actions, or unrelated repositories were touched.

### Checks / results

- Manual inspection confirmed `test_gemini_acceptance_smoke.py` validates the no-execute default, identifier validation, explicit execute opt-in, safe error contracts, and mocked execute dispatch without making a live model request.
- Validation runner update committed as `4c797e177bbb6d7ade8983db06afbec2d8a045f3`.
- No green test-run claim is made because the connector environment does not expose an executable checkout.
- During the audit, a pre-existing validator-regression inconsistency was found: `test_stageguard_validation_runner.py::test_validation_harness_gate_owns_runner_regressions` expects the `validation harness` gate to resolve only `test_stageguard_validation_runner.py`, while that gate intentionally also selects `test_validation_*.py`. This must be reconciled before promoting the consolidated runner as green.

### Decisions

1. Distinguish the safe Gemini acceptance **contract tests** from the credentialed live Gemini smoke itself. The former belong in dependency-light validation; the latter remains explicitly outside it.
2. Do not create an exclusion merely because a filename contains `acceptance`; admission is based on inspected behavior and side-effect boundaries.
3. Do not claim `--require-full-coverage` release readiness until the validator-regression ownership inconsistency is fixed and the command is executed in a real checkout.

### Blockers / unknowns

- The consolidated runner still requires execution in a real checkout.
- The validation-harness ownership regression described above is currently inconsistent with the runner's intentional `test_validation_*.py` ownership and is the immediate code-level blocker.
- Historical full-suite failures/errors still need classification from an executable checkout.
- Live Gemini acceptance remains intentionally credentialed and outside this dependency-light runner.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- Disposable private Cloud Run acceptance still requires suitable credentials/environment and Docker.

## Single best next step

Fix the validation-harness ownership model so `test_stageguard_validation_runner.py` and the `test_validation_*.py` ownership regressions have unambiguous gate ownership, add a current-inventory assertion for zero accidental unowned safe tests, then execute `scripts/run_stageguard_validation.py --require-full-coverage --keep-going` in the first available real checkout and classify any failures rather than weakening gates.

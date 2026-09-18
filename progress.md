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

## Latest run — 2026-09-18 — validation full-coverage contract

### Inspected at start

Read `progress.md` completely first, then inspected `scripts/run_stageguard_validation.py`, the complete runtime-test inventory exposed by the repository API, and an existing validation-ownership regression to preserve the repository's test-loading convention.

### Changes / actions

- Audited the current `runtime/tests/test_*.py` inventory against the consolidated validator's gate selectors.
- Added `runtime/tests/test_validation_full_coverage.py` as a validator-of-the-validator contract.
- The new regression requires every safe runtime test to have at least one intentional production-validation gate owner, so adding a dependency-light test without classifying it becomes fail-visible immediately.
- It also requires every declared gate to resolve at least one safe test, preventing stale/renamed patterns from silently turning a safety boundary into an empty gate.
- It verifies the execution plan de-duplicates overlapping ownership so an intentionally cross-cutting test still runs at most once.
- The new contract is itself automatically owned by the existing `validation harness` gate through the intentionally bounded `test_validation_*.py` selector.
- No live/credentialed test was newly admitted merely to satisfy coverage; the coverage contract operates on the runner's existing definition of safe repository-local runtime tests.
- No credentials, cloud resources, Docker, Grafana instances, remediation targets, GitHub Actions, or unrelated repositories were touched.

### Checks / results

- Repository API inventory was reconciled against the current gate patterns; no currently visible safe runtime test was identified as unowned after applying those selectors.
- New full-coverage regression committed as `ee4e70227875c7c10955094b8120b903918889d7`.
- No green execution claim is made because this connector environment does not expose an executable checkout; the new regression and consolidated runner still need repository execution.

### Decisions

1. Make full ownership a permanent regression rather than relying on occasional manual `--require-full-coverage` audits.
2. Preserve overlap where it expresses cross-cutting safety ownership, but require the execution plan to run each file once.
3. Keep genuinely live/credentialed acceptance outside this dependency-light boundary rather than weakening credential isolation to achieve a cosmetic coverage number.

### Blockers / unknowns

- The consolidated runner still requires execution in a real checkout.
- Historical full-suite failures/errors still need classification from an executable checkout.
- Live Gemini acceptance remains intentionally credentialed and outside this dependency-light runner.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- Disposable private Cloud Run acceptance still requires suitable credentials/environment and Docker.

## Single best next step

Run `scripts/run_stageguard_validation.py --require-full-coverage --keep-going` in the first available executable checkout; classify and fix every failure without weakening gate ownership or credential isolation, then use the resulting green dependency-light baseline to resume product-facing hardening.

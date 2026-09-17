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
- Consolidated validation resolves only direct non-symlink files under `runtime/tests`, fails closed on empty gates, is non-interactive and timeout-bounded, scrubs credentials/Python injection controls, disables user-site packages/bytecode writes, and tests its own harness first.

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected Windows-specific permission test skipped.
- Focused core/API/UI suite from the last executable repository run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating latest hardening/recovery work.
- Historical official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`; pinned `1.4.1` still requires a live smoke.
- Current connector-authored tests have not been repository-executed in this runner and are not treated as passing tests.

## Latest run — 2026-09-17 — incident lifecycle validation coverage

### Inspected at start

Read `progress.md` completely first. Inspected the consolidated validator, its self-tests, and the repository test inventory. The consolidated gate had become strong at validating its own execution boundary, timeline/audit disclosure, execution safety, and Grafana MCP contracts, but it did not directly select the core fail-closed incident lifecycle tests. That meant evidence-unavailable and recovery-recheck regressions could escape the recommended pre-live-smoke command.

### Changes / actions

- Added a first-class `incident lifecycle` validation gate.
- The gate explicitly covers anchored incident runtime, evidence-unavailable behavior, recovery rechecks, and transition-failure authority.
- Added a harness regression requiring representative API and anchored lifecycle contracts to remain selected, so future filename/layout drift fails the harness instead of silently reducing safety coverage.
- Preserved all existing path confinement, credential isolation, non-interactive execution, timeout, and no-CI/no-Docker behavior.
- No credentials, cloud resources, remediation targets, workflows, or unrelated repositories were touched.

### Checks / results

- Validator expansion committed as `9ee4d9b371f183279145836f26ed4cc2f115666e`.
- Harness coverage committed as `4bd2b9b974cbb103eaac9564cd75e493b695cfd1`.
- This connector environment does not expose an executable repository checkout, so no test-pass claim is made.
- GitHub Actions was intentionally not triggered as a substitute for local validation.

### Decisions

1. The recommended consolidated gate should exercise production lifecycle invariants, not only the mechanics of the validator and MCP boundary.
2. Evidence-unavailable abstention and fresh-evidence recovery are high-value fail-closed contracts and belong in the fast local safety gate.
3. Explicit representative filenames in the harness are intentional: if those critical contracts are renamed or removed, validation should demand a conscious update.

### Blockers / unknowns

- The expanded consolidated runner still requires execution in a real checkout.
- Historical full-suite failures/errors still need classification from an executable checkout.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- Disposable private Cloud Run acceptance still requires suitable credentials/environment and Docker.

## Single best next step

In an executable checkout, run `python scripts/run_stageguard_validation.py --list` and verify the new incident-lifecycle selection, then run `python scripts/run_stageguard_validation.py --keep-going`. Fix any failures before the pinned Grafana MCP 1.4.1 read-only live smoke.

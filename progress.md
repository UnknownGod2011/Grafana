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

## Latest run — 2026-09-17 — operator API boundary validation coverage

### Inspected at start

Read `progress.md` completely first, then inspected the repository tree, consolidated validator, and validator self-tests. The implementation already contains dedicated authentication/error-redaction, HTTP request-framing, protocol-preflight, identity, and HTTP-surface tests, but the recommended consolidated safety command did not explicitly own those production ingress contracts.

### Changes / actions

- Added a first-class `operator API boundary` validation gate before incident-lifecycle execution.
- The gate selects the base API contract plus authentication error redaction, protocol preflight, request framing, HTTP surface, and identity tests.
- Added an exact harness assertion for those six files so deletion/rename or accidental selection drift fails validation rather than silently weakening the ingress gate.
- Updated the validator module documentation to make the production-boundary coverage explicit.
- Preserved path confinement, credential isolation, user-site isolation, non-interactive subprocesses, bounded per-file execution, and no-CI/no-Docker behavior.
- No credentials, cloud resources, remediation targets, workflows, or unrelated repositories were touched.

### Checks / results

- Validator change committed as `3bf625ae6a6fa563cd734fadfb3574558264bb89`.
- Harness coverage committed as `a447f78535e9f7e776571998bb5e9fe485719bf6`.
- Repository inventory confirms all six selected operator-boundary test files exist on `main`.
- This connector environment does not expose an executable checkout, so no new test-pass claim is made.
- GitHub Actions was intentionally not triggered as a substitute for local validation.

### Decisions

1. Authentication and request/protocol framing are production mutation-boundary contracts and belong in the fast consolidated safety gate, not only the historical full suite.
2. This gate runs before lifecycle tests so obvious ingress regressions fail early.
3. Exact ownership is intentional because these six tests define a small, stable operator-facing trust boundary.

### Blockers / unknowns

- The expanded consolidated runner still requires execution in a real checkout.
- Historical full-suite failures/errors still need classification from an executable checkout.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- Disposable private Cloud Run acceptance still requires suitable credentials/environment and Docker.

## Single best next step

In an executable checkout, run `python scripts/run_stageguard_validation.py --list` and confirm the operator API boundary plus incident-lifecycle selections, then run `python scripts/run_stageguard_validation.py --keep-going`. Fix any failures before the pinned Grafana MCP 1.4.1 read-only live smoke.

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
- Consolidated validation resolves only direct non-symlink files under `runtime/tests`, fails closed on empty gates, is non-interactive and timeout-bounded, scrubs live credentials/proxies/Python injection controls, isolates Google ADC/gcloud homes and metadata identity, validates durable checkpoint/integrity contracts before operator mutation gates, explicitly validates remediation provider/transport/result contracts, executes overlapping selections once under their earliest owner, classifies subprocess launch failures as validation failures, and can audit/fail closed on safe runtime tests that are not owned by any production gate.

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected Windows-specific permission test skipped.
- Focused core/API/UI suite from the last executable repository run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating latest hardening/recovery work.
- Historical official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`; pinned `1.4.1` still requires a live smoke.
- Current connector-authored tests have not been repository-executed in this runner and are not treated as passing tests.

## Latest run — 2026-09-18 — validation ownership audit

### Inspected at start

Read `progress.md` completely first, then inspected the consolidated validation runner, its harness regression, the runtime tree, and the runtime test inventory. The validator intentionally runs a safety-focused subset, but there was no machine-visible way to tell which safe `runtime/tests/test_*.py` files were outside all gates. That makes future test additions easy to omit silently from the production-safety path.

### Changes / actions

- Added deterministic discovery of every direct, regular, non-symlink `runtime/tests/test_*.py` file.
- Added an ownership audit that computes tests not selected by any production validation gate.
- `--list` now prints an `unowned safe runtime tests` section, making validation-scope drift visible without changing the default execution contract.
- Added opt-in `--require-full-coverage`, which exits with configuration error code 2 before execution if any safe runtime test is unowned. This gives maintainers/acceptance scripts a fail-closed mode without forcing the dependency-light default validator to execute integration-heavy tests.
- Added harness regressions for deterministic unowned-test detection and fail-closed full-coverage behavior.
- Preserved existing credential isolation, per-file timeout, gate ordering, overlap de-duplication, and no-Docker/no-live-resource behavior.
- No credentials were read or supplied. No Docker, cloud resources, remediation targets, GitHub Actions, or unrelated repositories were touched.

### Checks / results

- Validation ownership implementation committed as `bf434efb3edada76f1a13eaa304a96deba772135`.
- Harness regressions committed as `a68cb6f698b8ff016a27b5c7fef6ec1c12e75106`.
- Static inspection confirms the new audit only considers safe direct `test_*.py` files and therefore does not widen execution to helpers, symlinks, or external paths.
- This connector environment does not expose an executable checkout, so no new green-test claim is made and GitHub Actions was intentionally not triggered as a substitute.

### Decisions

1. Make ownership drift observable by default in `--list`, but keep full-suite ownership enforcement opt-in because the consolidated runner is deliberately dependency-light and not every integration test belongs in it.
2. Fail before subprocess execution when `--require-full-coverage` finds drift, so strict acceptance cannot accidentally run a partial suite and appear successful.
3. Reuse the existing safe-file predicate for the ownership audit so reporting cannot be influenced by symlinked or out-of-tree files.

### Blockers / unknowns

- The consolidated runner still requires execution in a real checkout.
- The new `--list` output will reveal the exact current unowned test inventory only when run in a checkout; those tests should then be classified as production-gate candidates versus intentionally integration-only.
- Historical full-suite failures/errors still need classification from an executable checkout.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- Disposable private Cloud Run acceptance still requires suitable credentials/environment and Docker.

## Single best next step

In an executable checkout, run `python scripts/run_stageguard_validation.py --list`, classify every reported unowned safe runtime test, add genuinely production-critical contracts to explicit gates, then run `python scripts/run_stageguard_validation.py --keep-going`; only use `--require-full-coverage` once intentionally integration-only tests have either been assigned an appropriate gate or explicitly separated from the dependency-light safety inventory.

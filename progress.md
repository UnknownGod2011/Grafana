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
- Consolidated validation resolves only direct non-symlink files under `runtime/tests`, fails closed on empty gates, is non-interactive and timeout-bounded, scrubs credentials/Python injection controls, disables user-site packages/bytecode writes, tests its own harness first, and executes overlapping gate selections only once under their earliest owner.

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected Windows-specific permission test skipped.
- Focused core/API/UI suite from the last executable repository run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating latest hardening/recovery work.
- Historical official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`; pinned `1.4.1` still requires a live smoke.
- Current connector-authored tests have not been repository-executed in this runner and are not treated as passing tests.

## Latest run — 2026-09-17 — validation execution deduplication

### Inspected at start

Read `progress.md` completely first, then inspected the consolidated validator and its self-tests. The gate taxonomy intentionally overlaps: for example, execution-watchdog contracts can be selected by both operator-concurrency and execution-safety patterns, while audit timeline contracts can be selected by both timeline-disclosure and public-audit patterns. The validator previously executed every occurrence, meaning one test file could run more than once in a single safety pass. That increased validation time and repeated any test side effects without adding coverage.

### Changes / actions

- Added `_execution_plan()` to assign each concrete selected test file to its earliest owning gate.
- Later gates retain visibility of overlapping tests as `already covered` rather than silently dropping them.
- `--list` now reports overlaps explicitly with `[covered by earlier gate]`.
- Runtime gate headings report runnable and already-covered counts.
- Added a harness regression proving a shared test executes at most once and remains attributed to its earliest gate.
- Preserved each gate's raw selection semantics, including existing exact ownership assertions for operator API/concurrency and lifecycle coverage.
- Preserved path confinement, credential/Python-environment isolation, non-interactive execution, per-file timeouts, and no-CI/no-Docker behavior.
- No credentials, cloud resources, remediation targets, workflows, or unrelated repositories were touched.

### Checks / results

- Validator deduplication committed as `a848c4e8cbf3c684b255d439e365a8b0a8eb0b63`.
- Harness regression committed as `fd1b10480b0bbaddc0fd5ed3a29b7c0b26d9f53d`.
- Static inspection confirms deduplication happens only after all gates are resolved and empty-gate validation is performed, so overlap handling cannot turn an empty gate into a false green.
- This connector environment does not expose an executable checkout, so no new test-pass claim is made.
- GitHub Actions was intentionally not triggered as a substitute for local validation.

### Decisions

1. Overlapping safety taxonomy is useful for human comprehension, but duplicate subprocess execution is not useful coverage.
2. Earliest-gate ownership is deterministic because `GATES` is ordered and per-gate file selection is sorted.
3. Raw gate selections remain intact for harness assertions; deduplication applies only to the execution plan.

### Blockers / unknowns

- The consolidated runner still requires execution in a real checkout.
- Historical full-suite failures/errors still need classification from an executable checkout.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- Disposable private Cloud Run acceptance still requires suitable credentials/environment and Docker.

## Single best next step

In an executable checkout, run `python scripts/run_stageguard_validation.py --list` and confirm overlapping files are marked as already covered, then run `python scripts/run_stageguard_validation.py --keep-going`. Fix any failures before the pinned Grafana MCP 1.4.1 read-only live smoke.

# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the read-only runtime evidence plane. The implemented vertical slice includes deterministic telemetry, Prometheus/Loki/Grafana, official Grafana MCP access, bounded investigation and diagnosis, optional Gemini briefing, exact-revision approval, remediation adapters, telemetry-verified recovery, authenticated lifecycle state, checkpoint/audit integrity, operator UI, Cloud Run deployment hardening, watchdog observability, authenticated private metrics bridging, evidence-unavailable abstention, no-replay execution reconciliation, recovery-only Grafana rechecks, stdio-only Grafana MCP launchers, strict operator-API authentication/framing/protocol preflight, and a loopback reference remediation provider with idempotent writes plus read-only operation reconciliation.

Detailed older run history remains in Git history; this file keeps current invariants, validation baseline, latest run, blockers, and next step.

## Core invariants

- Grafana/MCP is read-only evidence access; infrastructure-write credentials remain isolated.
- Supported MCP deployment is stdio-only; compose exposes only the required read-only datasource/Prometheus/Loki evidence surface.
- MCP launcher configuration, peer metadata, diagnostics, and smoke configuration are bounded, terminal-safe, and credential-redacted before operator display.
- Direct official `grafana/mcp-grafana` Docker launches, including recognized Docker Hub aliases, must explicitly use stdio.
- Gemini is advisory and cannot mutate diagnosis, approval, remediation, or recovery state.
- Required evidence unavailability prevents briefing, approval, and execution from becoming actionable.
- Approval is exact-revision-bound and single-use; provider acceptance never counts as recovery.
- Fresh Grafana telemetry is required to verify recovery; `recovery_unverified` cannot replay remediation.
- Ambiguous remediation execution remains behind the execution-uncertainty barrier until durable reconciliation and fresh evidence resolve it.
- Durable checkpoint/audit failures fail closed; provider operation reconciliation is required where supported.
- Operator API and reference remediation provider reject ambiguous credential/body framing before mutation.
- Metric/Loki activation is policy-owned and versioned; HTTP callers cannot supply arbitrary Grafana queries or datasource identities.
- Operator timeline disclosure is allowlist-based. Reconciliation exposes only canonical bounded `result` and `reason`; provider bodies, operation IDs, targets, credentials, arbitrary metadata, and raw actor identities remain private.
- Timeline event identifiers are non-empty, terminal-safe strings bounded to 160 characters before policy lookup or reconciliation parsing.
- Static timeline values are bounded JSON scalars and terminal-safe; nested values, oversized strings, non-finite floats, and unbounded integers fail closed.
- Static timeline field policy itself is bounded to 64 unique, non-empty, terminal-safe string keys of at most 128 characters; malformed, duplicate, oversized, string-as-iterable, and non-terminating allowlists fail closed.
- Timeline display strings reject C0/C1 controls, DEL, Unicode line/paragraph separators, the complete Unicode `Cf` format-control category, and Unicode `Cs` surrogate code points.
- Timeline policy iterators and Mapping access are treated as untrusted extension/persistence behavior; ordinary read failures fail closed without partial disclosure.
- Static timeline projection reads each allowlisted Mapping value exactly once, avoiding membership/read TOCTOU behavior from custom persistence adapters.
- An absent static timeline policy may delegate to the canonical reconciliation projector; an explicitly configured null/malformed policy never does and fails closed.
- Consolidated local validation gates must resolve to concrete test files before execution; an empty safety gate is an error, never a passing result.
- The consolidated validation harness must execute its own regression suite before it can report a green result.

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected Windows-specific permission test skipped.
- Focused core/API/UI suite from the last executable repository run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating latest hardening/recovery work.
- Historical official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`; pinned `1.4.1` still requires a live smoke.
- Current connector-authored tests have not been repository-executed in this runner and are not treated as passing tests.

## Latest run — 2026-09-17 — validation harness self-verification

### Inspected at start

Read `progress.md` completely first, then inspected `scripts/run_stageguard_validation.py` and `runtime/tests/test_stageguard_validation_runner.py`. The consolidated runner had regressions for its selection and command behavior, but those regressions were not selected by any consolidated gate. A defect in the runner could therefore potentially coexist with a green result from the runner itself.

### Changes / actions

- Added an explicit `validation harness` gate selecting `test_stageguard_validation_runner.py`.
- Placed the harness gate first so fail-fast execution verifies the validator before relying on it for the safety/MCP gates.
- Updated runner documentation to state the self-verification contract.
- Added a regression asserting the harness gate owns exactly the runner regression file.
- Preserved the existing concrete-file resolution, empty-gate failure, deterministic deduplication, fail-fast/keep-going behavior, and no-Docker/no-credential/no-CI scope.
- No CI workflow, credential, cloud resource, remediation target, or unrelated repository was touched.

### Checks / results

- Validation harness self-verification committed as `4f5c14cbee4277e73a419198642265e66e5f3e37`.
- Ownership regression committed as `5e0e6930a4c35a7fac471702f7611683d13f3f50`.
- The connector runner still does not expose an executable repository checkout, so the updated runner and regression were not executed; no green-test claim is made.
- No GitHub Actions workflow was triggered as a substitute for local validation.

### Decisions

1. The validation harness is part of the safety boundary and must verify its own contracts in every consolidated run.
2. Run harness regressions first so fail-fast mode does not rely on an unverified validator to interpret later gates.
3. Keep live Docker/Grafana checks outside this dependency-light local gate.

### Blockers / unknowns

- The hardened consolidated runner and latest connector-authored tests still require execution in a real checkout.
- Historical full-suite failures/errors still need classification from an executable checkout.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- Disposable private Cloud Run acceptance still requires suitable credentials/environment and Docker.

## Single best next step

In an executable checkout, run `python scripts/run_stageguard_validation.py --list`, confirm `validation harness` is first and owns `test_stageguard_validation_runner.py`, then run `python scripts/run_stageguard_validation.py --keep-going`. Fix any selected-gate failures first; if all gates pass, run the pinned Grafana MCP 1.4.1 read-only live smoke, then classify the historical full-suite failures.

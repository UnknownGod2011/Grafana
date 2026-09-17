# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the read-only runtime evidence plane. The implemented vertical slice includes deterministic telemetry, Prometheus/Loki/Grafana, official Grafana MCP access, bounded investigation and diagnosis, optional Gemini briefing, exact-revision approval, remediation adapters, telemetry-verified recovery, authenticated lifecycle state, checkpoint/audit integrity, operator UI, Cloud Run deployment hardening, watchdog observability, authenticated private metrics bridging, evidence-unavailable abstention, no-replay execution reconciliation, recovery-only Grafana rechecks, stdio-only Grafana MCP launchers, strict operator-API authentication/framing/protocol preflight, and a loopback reference remediation provider with idempotent writes plus read-only operation reconciliation.

Detailed older run history remains in Git history; this file keeps current invariants, validation baseline, latest run, blockers, and next step.

## Core invariants

- Grafana/MCP is read-only evidence access; infrastructure-write credentials remain isolated.
- Supported MCP deployment is stdio-only; compose exposes only the required read-only datasource/Prometheus/Loki evidence surface.
- Gemini is advisory and cannot mutate diagnosis, approval, remediation, or recovery state.
- Required evidence unavailability prevents briefing, approval, and execution from becoming actionable.
- Approval is exact-revision-bound and single-use; provider acceptance never counts as recovery.
- Fresh Grafana telemetry is required to verify recovery; `recovery_unverified` cannot replay remediation.
- Ambiguous remediation execution remains behind the execution-uncertainty barrier until durable reconciliation and fresh evidence resolve it.
- Durable checkpoint/audit failures fail closed; provider operation reconciliation is required where supported.
- Operator API and reference remediation provider reject ambiguous credential/body framing before mutation.
- Metric/Loki activation is policy-owned and versioned; HTTP callers cannot supply arbitrary Grafana queries or datasource identities.
- Operator timeline disclosure is allowlist-based and bounded; reconciliation exposes only canonical `result` and `reason`, never provider bodies, operation IDs, targets, credentials, arbitrary metadata, or raw actor identities.
- Consolidated local validation gates resolve only concrete direct non-symlink regular files under `runtime/tests`; empty gates fail closed and the harness tests itself first.
- Every consolidated test subprocess is non-interactive and timeout-bounded (120 seconds default, 3600 maximum).
- Consolidated dependency-light validation children do not inherit Grafana/Gemini/Google/remediation/generic secret credentials or Python startup/import-path injection controls.
- Validation children explicitly disable Python user-site packages and bytecode writes so user-profile packages cannot silently participate and the checkout is not modified by `__pycache__` artifacts.

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected Windows-specific permission test skipped.
- Focused core/API/UI suite from the last executable repository run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating latest hardening/recovery work.
- Historical official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`; pinned `1.4.1` still requires a live smoke.
- Current connector-authored tests have not been repository-executed in this runner and are not treated as passing tests.

## Latest run — 2026-09-17 — validation user-site isolation

### Inspected at start

Read `progress.md` completely first, then inspected `scripts/run_stageguard_validation.py` and `runtime/tests/test_stageguard_validation_runner.py`. The runner already removed explicit Python path/startup controls, credentials, and interactive stdin, but Python could still import packages installed in the invoking user's site-packages directory. That weakens reproducibility and leaves an ambient-code path outside the repository despite `PYTHONPATH` scrubbing.

### Changes / actions

- Added forced validation environment overrides `PYTHONNOUSERSITE=1` and `PYTHONDONTWRITEBYTECODE=1`.
- Overrides are applied after inherited-environment sanitization, so an invoking shell cannot disable them with `PYTHONNOUSERSITE=0` or `PYTHONDONTWRITEBYTECODE=0`.
- User-site package loading is now disabled for every consolidated test subprocess, reducing ambient dependency/code injection from developer profiles.
- Bytecode writes are disabled so dependency-light validation does not leave `__pycache__` artifacts in the checkout.
- Added a runner regression proving hostile/disabled inherited values are replaced with the enforced values while ordinary environment variables remain available.
- Updated validator documentation to describe the stronger import isolation contract.
- No CI workflow, credential, cloud resource, remediation target, or unrelated repository was touched.

### Checks / results

- Validator hardening committed as `5097c384acb7b9dd3858880e718cfef89902df24`.
- Regression coverage committed as `f0ee9d3ac31bd94bf27ee2a703a48569a031b24b`.
- This connector environment still does not expose an executable repository checkout, so the new self-test was not executed and no green-test claim is made.
- No GitHub Actions workflow was triggered as a substitute for local validation.

### Decisions

1. Removing `PYTHONPATH` alone is not sufficient isolation because Python user-site packages are another ambient import source.
2. The validator remains dependency-light rather than using Python isolated mode (`-I`), which could alter repository import behavior; explicit user-site suppression is the narrower compatible control.
3. Validation should be read-like with respect to the checkout, so suppressing bytecode writes is appropriate.

### Blockers / unknowns

- The hardened consolidated runner and latest connector-authored tests still require execution in a real checkout.
- Historical full-suite failures/errors still need classification from an executable checkout.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- Disposable private Cloud Run acceptance still requires suitable credentials/environment and Docker.

## Single best next step

In an executable checkout, run `python scripts/run_stageguard_validation.py --list`, then `python scripts/run_stageguard_validation.py --keep-going`. Fix any selected-gate failures first; if all gates pass, run the pinned Grafana MCP 1.4.1 read-only live smoke with an explicitly scoped read-only credential, then classify the historical full-suite failures.

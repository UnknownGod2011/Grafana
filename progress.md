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
- Consolidated validation resolves only direct non-symlink files under `runtime/tests`, fails closed on empty gates, is non-interactive and timeout-bounded, scrubs Grafana/Gemini/Google credentials (including inline Google service-account JSON forms) and Python injection controls, disables user-site packages/bytecode writes, isolates well-known Google ADC/gcloud home locations during execution, tests its own harness first, validates runtime activation before operator/API gates, executes overlapping gate selections only once under their earliest owner, and classifies subprocess launch failures as validation failures.

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected Windows-specific permission test skipped.
- Focused core/API/UI suite from the last executable repository run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating latest hardening/recovery work.
- Historical official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`; pinned `1.4.1` still requires a live smoke.
- Current connector-authored tests have not been repository-executed in this runner and are not treated as passing tests.

## Latest run — 2026-09-17 — ambient Google ADC isolation

### Inspected at start

Read `progress.md` completely first, then inspected the current repository head, consolidated validator, and validator self-tests. Explicit Google credential environment variables were already scrubbed, but the validator still inherited the invoking user's `HOME`, `USERPROFILE`, and `CLOUDSDK_CONFIG`. Google Application Default Credentials can discover a well-known local ADC file beneath the user's home even when `GOOGLE_APPLICATION_CREDENTIALS` is absent, so ordinary local regression subprocesses still had a path to ambient developer credentials.

### Changes / actions

- Added per-run temporary-home isolation around executable validation.
- `_validation_env` now accepts an `isolated_home` and, when supplied by `main`, overrides `HOME`, `USERPROFILE`, and `CLOUDSDK_CONFIG` so child tests cannot discover the invoking developer's normal Google ADC/gcloud credential locations.
- Added regression coverage proving inherited POSIX home, Windows profile, and gcloud configuration paths are replaced while ordinary deterministic settings remain available.
- Kept `--list` side-effect-light: it resolves and prints the plan without creating an execution home because it launches no test subprocesses.
- No credentials were read or supplied. No Docker, cloud resources, remediation targets, GitHub Actions, or unrelated repositories were touched.

### Checks / results

- Validator hardening committed as `35500dc560b6926de54d6ad8a43f9e366965d2a7`.
- Regression coverage committed as `ed16da50ed3c09a93e2ff482b2243c2c8adc78f2`.
- Static inspection confirms executable validation constructs one empty temporary home for the run and passes the isolated environment to every selected subprocess.
- This connector environment does not expose an executable checkout, so the updated harness has not been repository-executed and no new green-test claim is made.
- GitHub Actions was intentionally not triggered as a substitute for local validation.

### Decisions

1. Treat well-known ADC discovery as part of the credential boundary, not only explicit credential environment variables.
2. Isolate both POSIX (`HOME`) and Windows (`USERPROFILE`) discovery plus `CLOUDSDK_CONFIG`, because StageGuard should validate safely on either developer platform.
3. Scope home isolation to actual test execution so `--list` remains a pure planning/inspection path.

### Blockers / unknowns

- The consolidated runner still requires execution in a real checkout.
- Historical full-suite failures/errors still need classification from an executable checkout.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- Disposable private Cloud Run acceptance still requires suitable credentials/environment and Docker.

## Single best next step

In an executable checkout, run `python scripts/run_stageguard_validation.py --list` and then `python scripts/run_stageguard_validation.py --keep-going`. Fix any failures before performing the pinned Grafana MCP 1.4.1 read-only live smoke.

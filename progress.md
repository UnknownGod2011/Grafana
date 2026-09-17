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
- Consolidated validation resolves only direct non-symlink files under `runtime/tests`, fails closed on empty gates, is non-interactive and timeout-bounded, scrubs Grafana/Gemini/Google credentials (including inline Google service-account JSON forms) and Python injection controls, disables user-site packages/bytecode writes, tests its own harness first, validates runtime activation before operator/API gates, executes overlapping gate selections only once under their earliest owner, and classifies subprocess launch failures as validation failures.

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected Windows-specific permission test skipped.
- Focused core/API/UI suite from the last executable repository run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating latest hardening/recovery work.
- Historical official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`; pinned `1.4.1` still requires a live smoke.
- Current connector-authored tests have not been repository-executed in this runner and are not treated as passing tests.

## Latest run — 2026-09-17 — inline Google credential isolation

### Inspected at start

Read `progress.md` completely first, then inspected the current repository head, consolidated validator, validator self-tests, and runtime test inventory. The validator already removed ADC file pointers, gcloud access-token overrides, Grafana/Gemini/API-key/remediation secrets, generic secret suffixes, and Python injection controls. It did not explicitly remove the common inline Google service-account credential environment forms `GOOGLE_CREDENTIALS` and `GOOGLE_CLOUD_KEYFILE_JSON`, either of which can contain the complete private-key JSON rather than a file path.

### Changes / actions

- Added `GOOGLE_CREDENTIALS` and `GOOGLE_CLOUD_KEYFILE_JSON` to the validator's exact sensitive-environment denylist.
- Extended the credential-isolation regression fixture with representative inline service-account JSON values and require both variables to be absent from the child validation environment.
- Extended case-insensitive sensitive-name coverage for both inline Google credential names.
- Kept ordinary Google project/location configuration untouched; the change targets credential-bearing forms rather than preventing tests from receiving non-secret runtime configuration.
- No credentials were read or supplied. No Docker, cloud resources, remediation targets, GitHub Actions, or unrelated repositories were touched.

### Checks / results

- Validator hardening committed as `71303013c71c22cc7019cb05c795e708d901d2a4`.
- Regression coverage committed as `9722e5e4c3f1b5d0d200eeed8fd79bd425d672cf`.
- Static inspection confirms the sensitive-name matcher is case-insensitive and the new names flow through the same `_validation_env` sanitization used for every test subprocess.
- This connector environment does not expose an executable checkout, so the updated harness has not been repository-executed and no new green-test claim is made.
- GitHub Actions was intentionally not triggered as a substitute for local validation.

### Decisions

1. Treat inline service-account JSON as equivalent in sensitivity to `GOOGLE_APPLICATION_CREDENTIALS`; local validation has no reason to inherit either form.
2. Use exact-name denial for these variables rather than a broad `GOOGLE_` prefix, because project IDs, regions, and other non-secret Google configuration can be legitimate deterministic test inputs.
3. Preserve the explicit live-smoke boundary: real Grafana/GCP credentials should only enter deliberate integration commands, never the dependency-light consolidated safety suite.

### Blockers / unknowns

- The consolidated runner still requires execution in a real checkout.
- Historical full-suite failures/errors still need classification from an executable checkout.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- Disposable private Cloud Run acceptance still requires suitable credentials/environment and Docker.

## Single best next step

In an executable checkout, run `python scripts/run_stageguard_validation.py --list` and then `python scripts/run_stageguard_validation.py --keep-going`. Fix any failures before performing the pinned Grafana MCP 1.4.1 read-only live smoke.
